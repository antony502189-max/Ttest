FROM node:22-alpine@sha256:c610fcdfb1d5b4740dd70c284ed3cb16bb857e0f7166196e36a5501df7a3aa32 AS frontend-build

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . ./

ARG VITE_API_BASE_URL=/api/v1
ARG VITE_ENABLE_MOCK_MODE=0
ARG VITE_BASE_PATH=/
ARG VITE_GOOGLE_MAPS_API_KEY=
ARG VITE_GOOGLE_MAPS_MAP_ID=
ARG VITE_GOOGLE_CLIENT_ID=
ARG VCS_REF=unknown
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL \
    VITE_ENABLE_MOCK_MODE=$VITE_ENABLE_MOCK_MODE \
    VITE_BASE_PATH=$VITE_BASE_PATH \
    VITE_GOOGLE_MAPS_API_KEY=$VITE_GOOGLE_MAPS_API_KEY \
    VITE_GOOGLE_MAPS_MAP_ID=$VITE_GOOGLE_MAPS_MAP_ID \
    VITE_GOOGLE_CLIENT_ID=$VITE_GOOGLE_CLIENT_ID
# The runtime image runs as the unprivileged nginx user.  A restrictive
# checkout umask can otherwise preserve 0600 build artifacts and turn direct
# static/legal URLs into 403 responses.
RUN npm run build \
    && npm run test:bundle-security \
    && printf '{"commit":"%s"}\n' "$VCS_REF" > dist/build-info.json \
    && find dist -type d -exec chmod 755 {} + \
    && find dist -type f -exec chmod 644 {} +

FROM nginxinc/nginx-unprivileged:1.27-alpine@sha256:65e3e85dbaed8ba248841d9d58a899b6197106c23cb0ff1a132b7bfe0547e4c0
ARG VCS_REF=unknown
LABEL org.opencontainers.image.revision=$VCS_REF
# Git worktrees may be checked out under a restrictive umask.  The pinned
# nginx-unprivileged image reads its configuration as the non-root nginx user,
# so make this runtime configuration explicitly world-readable.
COPY --chmod=644 deploy/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=frontend-build /app/dist /usr/share/nginx/html
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=3s --retries=5 CMD wget -qO- http://127.0.0.1:8080/ >/dev/null || exit 1
