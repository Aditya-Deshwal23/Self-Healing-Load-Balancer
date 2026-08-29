# Local Demonstration Steps

## Before Starting

Install Docker Desktop, OpenSSL, and use a Mac or Linux host. The helper script creates local secrets and a development certificate. Do not commit the generated `.secrets` or `.local-certs` directories.

## 1. Start the Lab

```sh
./local-up
```

**Expected output.** The script builds the services, waits for semantic health, and prints a local HTTPS URL. NGINX is the only service with published host ports: `8080` and `8443`.

## 2. Confirm Running Services

```sh
./local-status
docker compose ps
```

**Expected output.** NGINX, HAProxy, Prometheus, the API, the control worker, PostgreSQL, Redis, traffic generator, and backend instances A, B, and C should be running. HAProxy, backends, API, worker, and Prometheus should become healthy.

## 3. Open the Console

Open the URL printed by `./local-up`, accept the local certificate warning if needed, and sign in as `researcher@shlb.local`. Read the generated password from `.secrets/bootstrap_password`.

**Expected output.** The Command Center and route-by-instance matrix show live state. Application traffic is being generated in the background.

## 4. Verify Normal Traffic

Use the Traffic or System view. Optionally inspect the generated requests:

```sh
docker compose logs --tail=20 traffic-generator
```

**Expected output.** The traffic generator prints periodic JSON windows with successful response families for the four routes. HAProxy can send traffic to A, B, and C.

## 5. Inject the Supported Fault

In the console, open **Lab** and select **Checkout fails on Backend B**. Do not stop a backend container for this primary demonstration; this scenario is a route-specific application failure.

**Expected output.** Backend B returns failures only for checkout. Its public, auth, and catalog routes remain healthy. The injected fault has a bounded expiry.

## 6. Observe Detection

Wait for the control worker to collect its evidence window. Open **Incidents** and the **Decision Trace**.

**Expected output.** The worker records a `ROUTE_INSTANCE_FAILURE` classification when the required evidence is present. The trace shows request evidence, direct probes, safety inputs, and selected action details.

## 7. Observe the Recovery Action

Open **Actions** or the route-by-instance matrix.

**Expected output.** The worker prepares `ROUTE_MEMBERSHIP_QUARANTINE`, sets `be_checkout/srv_inst_b` to drain with weight zero through HAProxy Runtime, and reads the Runtime state back. Checkout traffic continues through A and C. B remains available for public, auth, and catalog.

## 8. Verify Recovery

Wait for the verification result. Optional command-line check:

```sh
./local-smoke
```

**Expected output.** Verification requires real checkout samples, acceptable checkout error rate, healthy peers, safe queue state, and matching desired/observed routing state. Zero samples are not treated as success.

## 9. Clear the Fault

Use the clear action in **Lab** for the active fault.

**Expected output.** The worker observes healthy direct probes and begins the recovery path. The incident moves from mitigation toward recovery.

## 10. Watch Staged Reintegration

Open **Recovery** and remain on the matrix view.

**Expected output.** Checkout membership for B moves through 5%, 20%, 50%, and 100% weights only after each stage passes its probes, traffic samples, and runtime readback. It then returns to a healthy state.

## Optional: Demonstrate a Container-Level Failure

For a separate infrastructure demonstration, stop one backend container:

```sh
docker compose stop demo-backend-b
docker compose start demo-backend-b
```

**Expected output.** HAProxy's health check marks the stopped backend unavailable. Starting it manually restores the container. Because Compose has `restart: unless-stopped`, an unexpected process exit can be restarted by Docker; the control worker itself does not restart containers. Use this as a separate health-check demonstration, not as the primary route-isolation flow.

## End the Session

```sh
./local-down
```

**Expected output.** Containers stop while local volumes and the development certificate remain for the next run.
