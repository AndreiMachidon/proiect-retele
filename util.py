from enum import Enum

class RequestMessageType(Enum):
  CONNECT = 1
  SEND_WMI_COMMAND = 2
  ADD_CLIENT = 3
  VIEW_CONTACTS = 4
  DISCONNECT = 5
  
class ResponseMessageStatus(Enum):
  OK = 1
  ERROR = 2


class Request:
  def __init__(self, type, params):
    self.type = type
    self.params = params

class Response:
  def __init__(self, status, payload):
    self.status = status
    self.payload = payload
    
def serialize(obj):
    if isinstance(obj, Request):
        params = ' '.join(obj.params) if obj.params else ''
        return bytes(f"REQ {obj.type.value} {params}", encoding='utf-8')
    elif isinstance(obj, Response):
        return bytes(f"RES {obj.status.value} {obj.payload}", encoding='utf-8')
    else:
        raise ValueError("Unsupported object type for serialization")

def deserialize(data):
    items = data.decode('utf-8').strip().split(' ')
    message_type = items[0]
    message_code = int(items[1])

    if message_type == "REQ":
        return Request(RequestMessageType(message_code), items[2:])
    elif message_type == "RES":
        payload = ' '.join(items[2:])
        return Response(ResponseMessageStatus(message_code), payload)
    else:
        raise ValueError("Unknown message type")