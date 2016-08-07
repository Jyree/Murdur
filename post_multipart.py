import mimetypes

from tornado.gen import coroutine, Return
from tornado.httpclient import HTTPRequest, AsyncHTTPClient

# from tornado_flickrapi.httpclient import fetch


@coroutine
def posturl(url, fields, files):
    try:
        response = yield post_multipart(url, fields, files)
    except Exception as e:
        raise e
    raise Return(response)


@coroutine
def post_multipart(url, fields, files):
    """
    Post fields and files to an http host as multipart/form-data.
    fields is a sequence of (name, value) elements for regular form fields.
    files is a sequence of (name, filename, value) elements for data to be
    uploaded as files.
    Return the server's response page.
    """
    content_type, body = encode_multipart_formdata(fields, files)
    headers = {"Content-Type": content_type, 'content-length': str(len(body))}
    request = HTTPRequest(url, "POST", headers=headers, body=body, validate_cert=False)

    try:
        response = yield AsyncHTTPClient().fetch(request)
    except Exception as e:
        raise e

    raise Return(response)


def encode_multipart_formdata(fields, files):
    """
    fields is a sequence of (name, value) elements for regular form fields.
    files is a sequence of (name, filename, value) elements for data to be
    uploaded as files.
    Return (content_type, body) ready for httplib.HTTP instance
    """
    BOUNDARY = b'----------ThIs_Is_tHe_bouNdaRY_$'
    CRLF = b'\r\n'
    L = []
    for (key, value) in fields:
        key = key.encode('utf8')
        value = str(value).encode('utf8')
        L.append(b'--' + BOUNDARY)
        L.append(b'Content-Disposition: form-data; name="%b"' % key)
        L.append(b'')
        L.append(value)
    for (key, filename, value) in files:
        filename = filename.encode("utf8")
        key = key.encode('utf8')

        L.append(b'--' + BOUNDARY)
        L.append(
            b'Content-Disposition: form-data; name="%b"; filename="%b"' % (
                key, filename
            )
        )
        L.append(('Content-Type: %s' % get_content_type(str(filename))).encode('utf8'))
        L.append(b'')
        L.append(value)
    L.append(b'--' + BOUNDARY + b'--')
    L.append(b'')
    body = CRLF.join(L)
    content_type = b'multipart/form-data; boundary=%b' % BOUNDARY
    return content_type, body


def get_content_type(filename):
    return mimetypes.guess_type(filename)[0] or 'application/octet-stream'
