import json
import urllib.request
import urllib.error


HOST = "127.0.0.1"
PORT = 8765


def request(
    method,
    path,
    data=None,
    headers=None,
):
    url = f"http://{HOST}:{PORT}{path}"

    body = None

    if data is not None:
        body = json.dumps(data).encode("utf-8")

    request = urllib.request.Request(
        url,
        data=body,
        method=method,
    )

    request.add_header(
        "Content-Type",
        "application/json",
    )

    if headers:
        for key, value in headers.items():
            request.add_header(key, value)

    try:
        with urllib.request.urlopen(request) as response:
            response_body = response.read().decode("utf-8")

            print(
                f"{method} {path} → {response.status}"
            )

            print(
                json.dumps(
                    json.loads(response_body),
                    indent=2,
                )
            )

            return json.loads(response_body)

    except urllib.error.HTTPError as error:
        response_body = error.read().decode("utf-8")

        print(
            f"{method} {path} → {error.code}"
        )

        print(response_body)

        return None


print()
print("DESK Companion pairing test")
print("----------------------------")
print()

code = input(
    "Enter the pairing code shown in DESK: "
).strip()

print()
print("Pairing device...")

pair_result = request(
    "POST",
    "/api/pair",
    {
        "code": code,
        "device_name": "DESK Test Device",
    },
)

if not pair_result or not pair_result.get("success"):
    print()
    print("Pairing failed.")
    raise SystemExit(1)

device = pair_result["device"]

device_id = device["device_id"]
token = device["token"]

print()
print("Pairing successful!")
print()
print("Device ID:")
print(device_id)
print()
print("Token:")
print(token)
print()

print("Testing authenticated status request...")
print()

request(
    "GET",
    "/api/status",
    headers={
        "X-DESK-Device-ID": device_id,
        "X-DESK-Token": token,
    },
)

print()
print("Testing authenticated agents request...")
print()

request(
    "GET",
    "/api/agents",
    headers={
        "X-DESK-Device-ID": device_id,
        "X-DESK-Token": token,
    },
)

print()
print("Testing authenticated workspace request...")
print()

request(
    "GET",
    "/api/workspace",
    headers={
        "X-DESK-Device-ID": device_id,
        "X-DESK-Token": token,
    },
)

print()
print("Pairing test complete.")
