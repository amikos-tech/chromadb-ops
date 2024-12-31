lint:
	@echo "Running pre-commit hooks"
	@pre-commit run --all-files
pre-commit:
	@echo "Linting last commit"
	@pre-commit run --from-ref HEAD~1 --to-ref HEAD
dependencies:
	@echo "Installing dependencies"
	@poetry update
install:
	@echo "Installing the project"
	@poetry install
test:
	@echo "Running tests"
	@poetry run pytest
build-docker:
	@echo "Building docker image"
	@docker build -t chromadb-dp .


.PHONY: go-test
go-test:
	@echo "Running tests"
	@go test --count=1 -v --tags "fts5" ./...


.PHONY: go-install
go-install:
	@go install -tags "fts5" -ldflags "-X 'main.Version=1.0.1-$$(git log -1 --format=%h)' -X 'main.BuildDate=$$(date +%Y-%m-%d)'"

.PHONY: go-lint
go-lint:
	@golangci-lint run

.PHONY: lint-fix
go-lint-fix:
	@golangci-lint run --fix ./...

.PHONY: go-build	
go-build:
	@go build -tags "fts5" -ldflags "-X 'main.Version=1.0.1' -X 'main.BuildHash=$$(git log -1 --format=%h)' -X 'main.BuildDate=$$(date +%Y-%m-%d)'" -o chops

.PHONY: go-binary-tarball
go-binary-tarball: go-build
	@tar -czf chops-${{ matrix.goos }}-${{ matrix.goarch }}.tar.gz chops

.PHONY: sqlc
sqlc:
	@echo "Generating SQLC code"
	@go install github.com/sqlc-dev/sqlc/cmd/sqlc@latest
	@sqlc generate
