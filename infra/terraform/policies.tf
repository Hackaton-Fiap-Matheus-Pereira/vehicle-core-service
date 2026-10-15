resource "kubernetes_network_policy_v1" "default_deny" {
  for_each = local.services

  metadata {
    name      = "default-deny"
    namespace = kubernetes_namespace_v1.domain[each.key].metadata[0].name
    labels    = local.common_labels
  }

  spec {
    pod_selector {}
    policy_types = ["Ingress", "Egress"]
  }
}

resource "kubernetes_network_policy_v1" "core_api" {
  metadata {
    name      = "allow-core-api"
    namespace = kubernetes_namespace_v1.domain["core"].metadata[0].name
    labels    = local.common_labels
  }

  spec {
    pod_selector {
      match_labels = {
        "app.kubernetes.io/name" = local.services.core.app_name
      }
    }
    policy_types = ["Ingress", "Egress"]

    ingress {
      ports {
        port     = "8000"
        protocol = "TCP"
      }
    }

    egress {
      to {
        namespace_selector {
          match_labels = {
            "kubernetes.io/metadata.name" = var.core_namespace
          }
        }
        pod_selector {
          match_labels = {
            "app.kubernetes.io/name" = local.services.core.mysql_name
          }
        }
      }
      ports {
        port     = "3306"
        protocol = "TCP"
      }
    }

    egress {
      to {
        namespace_selector {
          match_labels = {
            "kubernetes.io/metadata.name" = var.sales_namespace
          }
        }
        pod_selector {
          match_labels = {
            "app.kubernetes.io/name" = local.services.sales.app_name
          }
        }
      }
      ports {
        port     = "8000"
        protocol = "TCP"
      }
    }

    egress {
      to {
        namespace_selector {
          match_labels = {
            "kubernetes.io/metadata.name" = "kube-system"
          }
        }
      }
      ports {
        port     = "53"
        protocol = "UDP"
      }
      ports {
        port     = "53"
        protocol = "TCP"
      }
    }
  }
}

resource "kubernetes_network_policy_v1" "sales_api" {
  metadata {
    name      = "allow-sales-api"
    namespace = kubernetes_namespace_v1.domain["sales"].metadata[0].name
    labels    = local.common_labels
  }

  spec {
    pod_selector {
      match_labels = {
        "app.kubernetes.io/name" = local.services.sales.app_name
      }
    }
    policy_types = ["Ingress", "Egress"]

    ingress {
      ports {
        port     = "8000"
        protocol = "TCP"
      }
    }

    egress {
      to {
        namespace_selector {
          match_labels = {
            "kubernetes.io/metadata.name" = var.sales_namespace
          }
        }
        pod_selector {
          match_labels = {
            "app.kubernetes.io/name" = local.services.sales.mysql_name
          }
        }
      }
      ports {
        port     = "3306"
        protocol = "TCP"
      }
    }

    egress {
      to {
        namespace_selector {
          match_labels = {
            "kubernetes.io/metadata.name" = var.core_namespace
          }
        }
        pod_selector {
          match_labels = {
            "app.kubernetes.io/name" = local.services.core.app_name
          }
        }
      }
      ports {
        port     = "8000"
        protocol = "TCP"
      }
    }

    egress {
      to {
        namespace_selector {
          match_labels = {
            "kubernetes.io/metadata.name" = "kube-system"
          }
        }
      }
      ports {
        port     = "53"
        protocol = "UDP"
      }
      ports {
        port     = "53"
        protocol = "TCP"
      }
    }
  }
}

resource "kubernetes_network_policy_v1" "mysql" {
  for_each = local.services

  metadata {
    name      = "allow-${each.key}-database"
    namespace = kubernetes_namespace_v1.domain[each.key].metadata[0].name
    labels    = local.common_labels
  }

  spec {
    pod_selector {
      match_labels = {
        "app.kubernetes.io/name" = each.value.mysql_name
      }
    }
    policy_types = ["Ingress"]

    ingress {
      from {
        pod_selector {
          match_labels = {
            "app.kubernetes.io/name" = each.value.app_name
          }
        }
      }
      ports {
        port     = "3306"
        protocol = "TCP"
      }
    }
  }
}

