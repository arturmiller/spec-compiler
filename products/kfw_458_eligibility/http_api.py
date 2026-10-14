"""HTTP adapter for the authored applicant eligibility API contract."""

from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker, ValidationError

from app import evaluate


def _read_pointer(value: object, pointer: str) -> object:
    for part in pointer.split("/")[1:]:
        value = value[part.replace("~1", "/").replace("~0", "~")]
    return value


def _wrap_body(value: object, pointer: str) -> object:
    for part in reversed(pointer.split("/")[1:]):
        value = {part.replace("~1", "/").replace("~0", "~"): value}
    return value


def _unique_object(pairs):
    result = {}
    for name, value in pairs:
        if name in result:
            raise ValueError(f"Duplicate JSON key: {name}")
        result[name] = value
    return result


def _reject_constant(value):
    raise ValueError(f"Invalid JSON constant: {value}")


def create_handler(contract: dict, openapi: dict) -> type[BaseHTTPRequestHandler]:
    path, path_item = next(iter(openapi["paths"].items()))
    operation = path_item["post"]
    binding = operation["x-spec-compiler-binding"]
    if binding["invokes_contract"] != contract["decision_contract"]:
        raise ValueError("HTTP endpoint invokes a different Decision Contract")
    request_media, request_content = next(iter(operation["requestBody"]["content"].items()))
    success_status, invalid_status = binding["success_status"], binding["invalid_status"]
    success_media, success_content = next(iter(
        operation["responses"][str(success_status)]["content"].items()
    ))
    invalid_media, invalid_content = next(iter(
        operation["responses"][str(invalid_status)]["content"].items()
    ))
    request_validator = Draft202012Validator(
        request_content["schema"], format_checker=FormatChecker()
    )
    success_validator = Draft202012Validator(
        success_content["schema"], format_checker=FormatChecker()
    )
    invalid_validator = Draft202012Validator(
        invalid_content["schema"], format_checker=FormatChecker()
    )

    class Handler(BaseHTTPRequestHandler):
        def _send_json(self, status: int, value: object, media_type: str) -> None:
            body = (json.dumps(
                value, ensure_ascii=False, sort_keys=True, allow_nan=False
            ) + "\n").encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", f"{media_type}; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_invalid_request(self, message: str) -> None:
            body = _wrap_body(message, binding["error_pointer"])
            if not invalid_validator.is_valid(body):
                self._send_json(
                    500, {"error": "Error response violates the HTTP schema"}, "application/json"
                )
                return
            self._send_json(invalid_status, body, invalid_media)

        def do_GET(self) -> None:
            if self.path == "/openapi.json":
                self._send_json(200, openapi, "application/json")
            else:
                self._send_json(404, {"error": "Not found"}, "application/json")

        def do_POST(self) -> None:
            if self.path != path:
                self._send_json(404, {"error": "Not found"}, "application/json")
                return
            try:
                if self.headers.get_content_type() != request_media:
                    raise ValueError(f"Content-Type must be {request_media}")
                content_length = int(self.headers["Content-Length"])
                if content_length < 0:
                    raise ValueError("Content-Length must not be negative")
                body = json.loads(
                    self.rfile.read(content_length).decode("utf-8"),
                    object_pairs_hook=_unique_object, parse_constant=_reject_constant,
                )
                request_validator.validate(body)
                request = _read_pointer(body, binding["request_pointer"])
                result = evaluate(contract, request)
            except ValidationError as error:
                self._send_invalid_request(error.message)
                return
            except (KeyError, TypeError, ValueError, UnicodeDecodeError) as error:
                self._send_invalid_request(str(error))
                return
            body = _wrap_body(result, binding["result_pointer"])
            if not success_validator.is_valid(body):
                self._send_json(
                    500, {"error": "Decision Result violates the HTTP response schema"},
                    "application/json",
                )
                return
            self._send_json(success_status, body, success_media)

        def log_message(self, format: str, *args: object) -> None:
            pass

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--openapi", type=Path, required=True)
    args = parser.parse_args()
    contract = json.loads(args.contract.read_text(encoding="utf-8"))
    openapi = json.loads(args.openapi.read_text(encoding="utf-8"))
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ["PORT"])
    with ThreadingHTTPServer((host, port), create_handler(contract, openapi)) as server:
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
