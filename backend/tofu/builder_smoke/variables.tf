variable "vm_name" {
  description = "Nova 서버 이름 (afterglow-builder-<id>)"
  type        = string
}

variable "image_id" {
  description = "Nova 서버 이미지 UUID"
  type        = string
}

variable "flavor_id" {
  description = "Nova 서버 Flavor UUID"
  type        = string
}

variable "network_id" {
  description = "서버를 연결할 내부 네트워크 UUID"
  type        = string
}

variable "keypair_name" {
  description = "SSH 키페어 이름"
  type        = string
}

variable "user_data_b64" {
  description = "base64 인코딩된 cloud-init 스크립트"
  type        = string
}

variable "floating_network_id" {
  description = "FIP 를 할당할 외부 네트워크 UUID. 비워두면 FIP 미생성."
  type        = string
  default     = ""
}

variable "share_name" {
  description = "Manila share 이름"
  type        = string
}

variable "share_proto" {
  description = "Manila 공유 프로토콜: NFS 또는 CEPHFS"
  type        = string
  validation {
    condition     = contains(["NFS", "CEPHFS"], var.share_proto)
    error_message = "share_proto 는 NFS 또는 CEPHFS 여야 합니다."
  }
}

variable "size_gb" {
  description = "Manila share 크기 (GiB)"
  type        = number
  default     = 1
}

variable "share_type" {
  description = "Manila share type 이름"
  type        = string
}

variable "share_network_id" {
  description = "Manila share network UUID (NFS DHSS=true 시 필요). CEPHFS 또는 DHSS=false 시 비워둠."
  type        = string
  default     = ""
}
