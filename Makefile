# Development containers, one per family. Nothing is pushed: images stay in the
# local Docker store (publication: .github/workflows/publish.yml).
#   make avr | esp32 | stm32 | nrf52 | base   build one image for this machine
#   make test-<family>                        build it, then tests/test-image.sh
#                                             (esp32: also tests/test-esp32-rfc2217.sh)
#   make vscode-<family>                      extensions through the VS Code server over SSH
#   make clean-<family>                       remove its image
FAMILIES := avr esp32 stm32 nrf52
VERSION ?= dev
# Toolchain images (picodev-lab-workers/toolchains), built from this commit: fetched
# from WORKERS_REPO (workers.mk), or toolchains/ at this commit in the public mirror.
-include workers.mk
WORKERS_REF ?= 8559bde8b5f411f357e4e909c82cdbb944bbf86e
WORKERS := .toolchains/$(WORKERS_REF)
export VERSION

# test-%, vscode-% and clean-% stay out of .PHONY: make skips pattern rules for phony targets.
.PHONY: base $(FAMILIES) toolchains

# .toolchains/toolchains: the build context docker-bake.hcl reads, at WORKERS_REF.
ifneq ($(wildcard toolchains/.),)
toolchains:
	mkdir -p .toolchains && ln -sfn ../toolchains .toolchains/toolchains
else
toolchains: $(WORKERS)/.done
	ln -sfn $(WORKERS_REF)/toolchains .toolchains/toolchains
endif
$(WORKERS)/.done:
	rm -rf $(WORKERS) && git init -q $(WORKERS)
	git -C $(WORKERS) fetch -q --depth 1 $(WORKERS_REPO) $(WORKERS_REF)
	git -C $(WORKERS) checkout -q FETCH_HEAD && touch $@

base:
	docker buildx bake --load dev-base

$(FAMILIES): %: toolchains
	docker buildx bake --load dev-$*

test-%: %
	tests/test-image.sh $* dev-$*:$(VERSION)
	[ $* != esp32 ] || tests/test-esp32-rfc2217.sh dev-esp32:$(VERSION)
	[ ! -x tests/test-picodev.sh ] || case $* in avr|nrf52|stm32|esp32) tests/test-picodev.sh $* dev-$*:$(VERSION) ;; esac

vscode-%:
	tests/test-vscode-server.sh $* dev-$*:$(VERSION)

clean-%:
	docker rmi -f dev-$*:$(VERSION)
