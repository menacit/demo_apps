# Build container
FROM docker.io/library/golang:1.23.5-alpine AS builder

WORKDIR /go/src/favorites
COPY go.mod .
RUN go get github.com/rqlite/gorqlite
COPY main.go .

# Ensures that built binary is static
RUN CGO_ENABLED=0 GOOS=linux go build \
  -a -tags netgo -ldflags '-w -extldflags "-static"' \
  -o favorites_server

# Runtime container
FROM scratch

WORKDIR /
COPY --from=builder /go/src/favorites/favorites_server .

USER 10000
CMD ["/favorites_server"]

EXPOSE 8000
