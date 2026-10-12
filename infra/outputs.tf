output "public_ip" {
  value = oci_core_instance.vm.public_ip
}

output "ssh" {
  value = "ssh ubuntu@${oci_core_instance.vm.public_ip}"
}

output "tunnel_dashboards" {
  value = "ssh -L 18789:localhost:18789 -L 9119:localhost:9119 ubuntu@${oci_core_instance.vm.public_ip}"
}
