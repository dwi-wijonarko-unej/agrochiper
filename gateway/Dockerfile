FROM golang:1.22-alpine AS builder

WORKDIR /app
COPY go.mod .
COPY main.go .
RUN go build -o gateway main.go

FROM alpine:3.20
WORKDIR /app
COPY --from=builder /app/gateway /app/gateway
EXPOSE 8080
CMD ["/app/gateway"]
