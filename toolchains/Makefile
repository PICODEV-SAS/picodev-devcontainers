# Toolchain images, one per family. Run from toolchains/.
#   make test               images for this machine, then every test
#   make images-multiarch   amd64 and arm64 (arm64 under QEMU on an amd64 host)
#   make measure            sizes and build times, as AsciiDoc tables
# Nothing is pushed: images stay in the local Docker store.
FAMILIES := avr arm zephyr esp
TAG ?= dev
PLATFORMS ?= linux/amd64,linux/arm64

.PHONY: images images-multiarch unit test measure

images: $(FAMILIES:%=image-%)

image-%:
	docker buildx build -f $*/Dockerfile --load -t picodev-lab-toolchain-$*:$(TAG) .

images-multiarch:
	for f in $(FAMILIES); do \
	  docker buildx build -f $$f/Dockerfile --platform $(PLATFORMS) --load \
	    -t picodev-lab-toolchain-$$f:$(TAG) . || exit 1; \
	done

unit:
	python3 -m unittest discover -s tests -p test_tc.py

test: images
	python3 -m unittest discover -s tests -v

measure:
	python3 tests/measure.py
