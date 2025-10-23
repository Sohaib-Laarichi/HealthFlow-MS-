FROM maven:3.9.6-eclipse-temurin-17 AS builder

LABEL maintainer="HealthFlow-MS Team"
LABEL service="proxyfhir-builder"

WORKDIR /workspace

# Copy sources and pom
COPY pom.xml .
COPY src ./src

# Build the application (skip tests for faster iteration)
RUN mvn -B -DskipTests package

# --- Runtime image ---
FROM eclipse-temurin:17-jdk-alpine

LABEL maintainer="HealthFlow-MS Team"
LABEL service="proxyfhir"

WORKDIR /app

# Install curl for healthcheck
RUN apk add --no-cache curl

# Create app user for security
RUN addgroup -g 1001 -S appgroup && \
    adduser -u 1001 -S appuser -G appgroup

# Copy the built JAR from the builder stage
COPY --from=builder /workspace/target/*.jar app.jar

# Change ownership of the app
RUN chown -R appuser:appgroup /app

# Switch to non-root user
USER appuser

# Expose port used by the application
EXPOSE 8080

# Health check (uses curl installed above)
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD curl -f http://localhost:8080/actuator/health || exit 1

# Run the application
ENTRYPOINT ["java", "-Djava.security.egd=file:/dev/./urandom", "-jar", "app.jar"]