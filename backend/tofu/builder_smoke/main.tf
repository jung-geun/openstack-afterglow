terraform {
  required_providers {
    openstack = {
      source  = "terraform-provider-openstack/openstack"
      version = "~> 2.0"
    }
  }
  # PoC: local 백엔드. 운영 확장 시 swift 백엔드로 전환.
  backend "local" {}
}

provider "openstack" {
  # OS_AUTH_URL, OS_USERNAME, OS_PASSWORD 등 환경변수에서 자동으로 읽힘.
}

# ── Nova 서버 ────────────────────────────────────────────────────────────────

resource "openstack_compute_instance_v2" "builder" {
  name      = var.vm_name
  image_id  = var.image_id
  flavor_id = var.flavor_id
  key_pair  = var.keypair_name
  user_data = base64decode(var.user_data_b64)

  metadata = {
    union_type        = "ephemeral-builder"
    afterglow_managed = "true"
  }

  network {
    uuid = var.network_id
  }
}

# ── Floating IP (조건부) ─────────────────────────────────────────────────────

resource "openstack_networking_floatingip_v2" "fip" {
  count = var.floating_network_id != "" ? 1 : 0
  pool  = var.floating_network_id
}

resource "openstack_networking_floatingip_associate_v2" "fip_assoc" {
  count       = var.floating_network_id != "" ? 1 : 0
  floating_ip = openstack_networking_floatingip_v2.fip[0].address
  port_id     = openstack_compute_instance_v2.builder.network[0].port
}

# ── Manila Share ─────────────────────────────────────────────────────────────

resource "openstack_sharedfilesystem_share_v2" "share" {
  name        = var.share_name
  share_proto = var.share_proto
  size        = var.size_gb
  share_type  = var.share_type

  # DHSS=true(NFS) 환경에서만 share_network_id 필요
  share_network_id = var.share_network_id != "" ? var.share_network_id : null
}

# ── Manila Access Rule ───────────────────────────────────────────────────────

resource "openstack_sharedfilesystem_share_access_v2" "access" {
  share_id     = openstack_sharedfilesystem_share_v2.share.id
  access_type  = var.share_proto == "NFS" ? "ip" : "cephx"
  access_to    = var.share_proto == "NFS" ? openstack_compute_instance_v2.builder.network[0].fixed_ip_v4 : "builder-${var.vm_name}"
  access_level = "rw"

  # 서버가 ACTIVE 된 후 access rule 을 등록
  depends_on = [openstack_compute_instance_v2.builder]
}
