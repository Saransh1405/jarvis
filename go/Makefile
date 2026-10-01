run:
	cd cmd/gateway && go run .

dev down test-all:
	$(MAKE) -C .. $@

build:
	go build -o bin/gateway ./cmd/gateway

test:
	go test ./...

tidy:
	go mod tidy

.PHONY: run build test tidy dev down test-all
