FROM haproxytech/haproxy:alpine-s6-3.2.21@sha256:cc482e1018fe7814c0e8e561989167a1e86eea041a81709b0384428ba7fc06f0

# Phase 1's host-side validator streams Runtime commands through this local
# Unix-socket client. The socket is never exposed over TCP.
RUN apk add --no-cache socat

# This prototype performs only predeclared Runtime API mutations. Disable the
# bundled Data Plane API process so no structural admin listener or credential
# exists in the compact LAB profile.
RUN rm -f /etc/s6-overlay/s6-rc.d/user/contents.d/dataplaneapi
