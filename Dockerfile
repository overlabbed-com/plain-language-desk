# syntax=docker/dockerfile:1

# Builder: the full toolchain installs the package and its pure-python
# dependencies into a target directory. Nothing from this stage survives.
# The builder's python version must match the runtime image's — compiled
# wheels are ABI-bound (a cp312 wheel will not load on a 3.15 runtime).
FROM python:3.13-slim@sha256:2d44738ebf4ce5f63b9d9ea871e9c7cfdc0426f7b0c97cac915fd88ded1d86bb AS builder
WORKDIR /build
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir --target=/app/site-packages .

# Runtime: distroless python3-debian13:nonroot — non-root (uid 65532) by
# default, no shell, no package manager, pinned python minor (3.13).
# The digest pins the build this repo was verified against (2026-11-01);
# refresh it deliberately — rebuild, scan, re-pin — never by pulling a
# moving tag.
FROM gcr.io/distroless/python3-debian13@sha256:1c32c3720dc4c7f0c7dbe998737f32c200add6511eca7cec705008be488b87d6
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/site-packages
WORKDIR /app
COPY --from=builder /app/site-packages /app/site-packages
EXPOSE 8080
ENTRYPOINT ["/usr/bin/python3", "-m", "plain_language_desk"]
