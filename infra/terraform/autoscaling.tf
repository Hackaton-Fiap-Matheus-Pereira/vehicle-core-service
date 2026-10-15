resource "kubernetes_horizontal_pod_autoscaler_v2" "sales" {
  metadata {
    name      = local.services.sales.app_name
    namespace = kubernetes_namespace_v1.domain["sales"].metadata[0].name
    labels    = local.common_labels
  }

  spec {
    min_replicas = var.sales_replicas
    max_replicas = var.sales_max_replicas

    scale_target_ref {
      api_version = "apps/v1"
      kind        = "Deployment"
      name        = kubernetes_deployment_v1.app["sales"].metadata[0].name
    }

    metric {
      type = "Resource"
      resource {
        name = "cpu"
        target {
          type                = "Utilization"
          average_utilization = 70
        }
      }
    }
  }
}

