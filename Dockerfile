FROM golang:1.25-alpine AS builder

WORKDIR /app

RUN apk add --no-cache git

COPY go.mod go.sum ./
RUN go mod download

COPY . .

RUN CGO_ENABLED=0 GOOS=linux go build -o /ad-server ./cmd/api

FROM alpine:latest

WORKDIR /app

RUN apk --no-cache add ca-certificates

COPY --from=builder /ad-server .

COPY data/ ./data/

RUN mkdir -p ./internal/contextextractor/config
COPY --from=builder /app/internal/contextextractor/config/ ./internal/contextextractor/config/

EXPOSE 8090

CMD ["./ad-server"]
