output "core_url" {
  description = "URL local do Core por meio do mapeamento Kind/NodePort."
  value       = "http://localhost:8000"
}

output "sales_url" {
  description = "URL local do Sales por meio do mapeamento Kind/NodePort."
  value       = "http://localhost:8001"
}

output "service_dns" {
  description = "Nomes DNS usados na comunicação interna."
  value = {
    core  = "vehicle-core-service.${var.core_namespace}.svc.cluster.local:8000"
    sales = "vehicle-sales-service.${var.sales_namespace}.svc.cluster.local:8000"
  }
}

output "namespaces" {
  description = "Namespaces criados para manter os domínios segregados."
  value = {
    core  = kubernetes_namespace_v1.domain["core"].metadata[0].name
    sales = kubernetes_namespace_v1.domain["sales"].metadata[0].name
  }
}

