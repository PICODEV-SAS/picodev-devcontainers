# dev-<family> = toolchain image of picodev-lab-workers (pinned in the Makefile)
# + development layer (base/) + family layer (<family>/). `make` fetches the
# toolchains build context into TOOLCHAINS first.

variable "VERSION" { default = "dev" }
# "ghcr.io/picodev-sas/" to publish; empty for local images.
variable "REGISTRY" { default = "" }
variable "TOOLCHAINS" { default = ".toolchains/toolchains" }
variable "REVISION" { default = "" }
variable "CREATED" { default = "" }

# family: devcontainer name; toolchain: picodev-lab-workers image it starts from.
variable "FAMILIES" {
  default = [
    { family = "avr", toolchain = "avr" },
    { family = "esp32", toolchain = "esp" },
    { family = "stm32", toolchain = "arm" },
    { family = "nrf52", toolchain = "zephyr" },
  ]
}

target "_oci" {
  args = { VERSION = VERSION }
  labels = {
    "org.opencontainers.image.revision" = REVISION
    "org.opencontainers.image.created" = CREATED
  }
}

target "toolchain" {
  name = "toolchain-${f.toolchain}"
  matrix = { f = FAMILIES }
  context = TOOLCHAINS
  dockerfile = "${f.toolchain}/Dockerfile"
}

target "dev-base" {
  inherits = ["_oci"]
  context = "base"
  tags = ["${REGISTRY}dev-base:${VERSION}"]
}

target "layer" {
  name = "layer-${f.family}"
  matrix = { f = FAMILIES }
  inherits = ["_oci"]
  context = "base"
  contexts = { toolchain = "target:toolchain-${f.toolchain}" }
  args = { BASE = "toolchain" }
}

target "dev" {
  name = "dev-${f.family}"
  matrix = { f = FAMILIES }
  inherits = ["_oci"]
  context = f.family
  contexts = { layer = "target:layer-${f.family}" }
  args = { BASE = "layer" }
  tags = ["${REGISTRY}dev-${f.family}:${VERSION}"]
}

group "default" {
  targets = ["dev-base", "dev-avr", "dev-esp32", "dev-stm32", "dev-nrf52"]
}
