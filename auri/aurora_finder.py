from typing import Generator, Tuple, Union

import socket
import select

SSDP_ST = "nanoleaf_aurora:light"
Socket = socket.socket


def _parse_aurora_from_response(response: str) -> Union[str, None]:
    if response is None or SSDP_ST not in response:
        return
    for line in response.split("\n"):
        if "Location:" not in line:
            continue
        new_location = line.replace("Location:", "").strip().replace("http://", "").replace(":16021", "")
        return new_location


def _get_deviceid_from_response(response: str) -> str:
    for line in response.split("\n"):
        if "deviceid:" not in line:
            continue
        return line.replace("nl-deviceid:", "").strip()


def _get_response(sock: Socket) -> str:
    try:
        ready = select.select([sock], [], [], 5)
        if ready[0]:
            response = sock.recv(1024).decode("utf-8")
            return response
    except socket.error:
        sock.close()
        raise


def _prepare_socket() -> Socket:
    SSDP_IP = "239.255.255.250"
    SSDP_PORT = 1900
    SSDP_MX = 3
    request = ['M-SEARCH * HTTP/1.1',
               'HOST: ' + SSDP_IP + ':' + str(SSDP_PORT),
               'MAN: "ssdp:discover"',
               'ST: ' + SSDP_ST,
               'MX: ' + str(SSDP_MX)]
    request = '\r\n'.join(request).encode('utf-8')
    aurora_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    aurora_socket.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, SSDP_MX)
    aurora_socket.bind((socket.gethostname(), 9090))
    aurora_socket.sendto(request, (SSDP_IP, SSDP_PORT))
    aurora_socket.setblocking(False)
    return aurora_socket


def find_aurora_addresses(search_for_amount: int = 10) -> Generator[Tuple[str, str], None, None]:
    """
    Returns a list of the IP addresses of all Auroras found on the network

    """

    auroras = []
    aurora_socket = _prepare_socket()
    while len(auroras) < search_for_amount:
        response = _get_response(aurora_socket)
        aurora = _parse_aurora_from_response(response)
        if aurora is None or aurora in auroras:
            continue
        auroras.append(aurora)
        yield aurora, _get_deviceid_from_response(response)

    return
