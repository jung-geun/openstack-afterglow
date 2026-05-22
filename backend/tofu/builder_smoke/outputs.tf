output "server_id" {
  description = "Nova 서버 UUID"
  value       = openstack_compute_instance_v2.builder.id
}

output "internal_ip" {
  description = "서버 내부 Fixed IP (NFS access rule 등록됨)"
  value       = openstack_compute_instance_v2.builder.network[0].fixed_ip_v4
}

output "ssh_host" {
  description = "SSH 접속 주소 (FIP 또는 Fixed IP)"
  value       = var.floating_network_id != "" ? openstack_networking_floatingip_v2.fip[0].address : openstack_compute_instance_v2.builder.network[0].fixed_ip_v4
}

output "fip_id" {
  description = "FIP UUID (정리용). FIP 미사용 시 빈 문자열."
  value       = var.floating_network_id != "" ? openstack_networking_floatingip_v2.fip[0].id : ""
}

output "share_id" {
  description = "Manila share UUID"
  value       = openstack_sharedfilesystem_share_v2.share.id
}

output "access_key" {
  description = "CephX access key (CEPHFS 전용). NFS 시 빈 문자열."
  value       = var.share_proto == "CEPHFS" ? openstack_sharedfilesystem_share_access_v2.access.access_key : ""
  sensitive   = true
}
