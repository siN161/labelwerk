import os
import socket
import threading

import pytest

from labelwerk.media import (STATUS_REQUEST, Media, MediaError, label_for_media, parse_media,
                             query_status)


def status(width=62, media_code=0x0A, length=0, error2=0):
    """32-byte status response of a QL-600 (as measured on the real device)."""
    data = bytearray(32)
    data[0:3] = b"\x80\x20\x42"
    data[3], data[4] = 0x34, 0x47          # series/model QL-600
    data[9] = error2
    data[10], data[11], data[17] = width, media_code, length
    return bytes(data)


def test_parse_endless():
    assert parse_media(status()) == Media(62, 0, "endless")


def test_parse_die_cut():
    assert parse_media(status(width=62, media_code=0x0B, length=29)) == Media(62, 29, "die_cut")


def test_parse_no_media():
    assert parse_media(status(width=0, media_code=0x00)).kind == "none"


def test_parse_printer_error():
    with pytest.raises(MediaError, match="Replace media error"):
        parse_media(status(error2=0x01))


def test_parse_garbage():
    with pytest.raises(MediaError, match="Unverständliche Antwort"):
        parse_media(b"\x00" * 5)


def test_describe():
    assert Media(62, 0, "endless").describe() == "62 mm endlos"
    assert Media(62, 29, "die_cut").describe() == "62 × 29 mm gestanzt"
    assert Media(0, 0, "none").describe() == "keine Rolle eingelegt"


def test_label_for_media():
    assert label_for_media(Media(62, 0, "endless")) == "62"
    assert label_for_media(Media(62, 29, "die_cut")) == "62x29"
    assert label_for_media(Media(24, 24, "die_cut")) == "d24"
    assert label_for_media(Media(0, 0, "none")) is None
    assert label_for_media(Media(61, 0, "endless")) is None


def _fake_printer(reply):
    """Socket pair: our end for query_status, a fake printer answers at the other end."""
    ours, theirs = socket.socketpair()
    received = []

    def serve():
        data = b""
        while len(data) < len(STATUS_REQUEST):
            data += theirs.recv(4096)
        received.append(data)
        if reply:
            theirs.sendall(reply)

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    fd = os.dup(ours.fileno())
    os.set_blocking(fd, False)
    ours.close()
    return (lambda path: fd), received, thread, theirs


def test_query_status_sends_request_and_reads_reply():
    opener, received, thread, other = _fake_printer(status())
    data = query_status("file:///dev/usb/lp9", timeout=2, opener=opener)
    thread.join(1)
    other.close()
    assert received == [STATUS_REQUEST]
    assert parse_media(data) == Media(62, 0, "endless")


def test_query_status_times_out():
    opener, _, thread, other = _fake_printer(reply=None)
    with pytest.raises(MediaError, match="Keine Antwort"):
        query_status("file:///dev/usb/lp9", timeout=0.2, opener=opener)
    other.close()


def test_query_status_only_for_kernel_device():
    with pytest.raises(MediaError, match="nur über /dev/usb/lpN"):
        query_status("usb://0x04f9:0x20c0")


def test_query_status_missing_device(tmp_path):
    with pytest.raises(MediaError, match="nicht gefunden"):
        query_status(f"file://{tmp_path}/lp9")


def test_parse_unknown_media_code():
    with pytest.raises(MediaError, match=r"Unbekannte Rolle \(Code 0x77\)"):
        parse_media(status(media_code=0x77))
