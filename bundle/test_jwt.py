import jwt
import time

private_key = """-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEA2okOHspNjgA+2rTLbeuYcxiP/hG8C6Sb9iwg3yiLAA4HCnpI
TcbWCSelbvbYGuc3EbNy4xFyf5Cbj5DHJMIDEkryOgyd2giIIIBOUBj8S63uGcnR
pOBh9NFatfNwheKuzsPuVNldu6A9cNteNpXcWyJjG2axVfmq7i6SuKr1JoWYG7xT
TAvKPujSl4OtsQfO3h5NepzdfXpr28oNnzfWed+zclR6BcmNNo/WVfJ4xyCLSf0B
COgdTgW6PdaChd1l9VDetJZVEgC5tkyvXsfISI6iyrYbKR0NEBSqq4XkadEjsCs4
F1RncsS4LlgniT7GlkL9Mce3b0wGLs9/7ZIXdQIDAQABAoIBAHXqETKGJAmHZv/I
3AN7Dq8e1FyldfqUQ3n2C7FY9FgbN5w/6+SnQkRYld8VfW5WDAmGLCkEDa9yLYYm
Qa7s6S4mJ1HLnZGn0Nh7h9J6aG9jObBSGjyHgEcmFOvPNlXPqjDVBGmDSAcVKK0I
vA3EDvHliMLt+9gGpQmZ5K6B3KwT3rZIFZqOUGyu1BGi8tnXgL3ScSA4FIwPAj0g
z0NOG6B0OW0m3w63O3lsTYXQ+PSkFLMY08zKHBstmnBQ3TLC7X4UTQqkSSYRKJjH
97mPCTLXGPEJvkBr6q5HSq2tAiNfE14ObWM+UAzPqa94tWvLRb3KBrjqGb0B+5fY
FYxh7kECgYEA7yNQfTBFVqH6tTK8SI6/0tsUWJf2qNo35Sox0HMo2CRaPFxYHB08
Myq/3Q6tQUsjJABLcCqHSX8+Rj3/ecK3MJnQEEbAL3HP8N1WPP6/XZQZfSdo22s8
PNc/Z5vKX5KdHWJskV/VkBk3RiwO4YID0VxAUCOp8v3udHTXFnqH5KkCgYEA6cE8
A+r3n2h0VQJY8pHyBggr+RZRBb98TDU6iW2PR9F0SUqQGDflAJUOUgKpFuF62BRZ
CKnw/fQX5mNGqqyPyJQ5V4rNtSRX4PSG7uLxrFn2pPLZJ95qKpVLcPmfnHuj29n5
BDcm5HSBnnXBg2qDEJ3BQHtqLsBpBM/7PCPY2e0CgYEAyYQeRF+mRxMsC/z55i3s
fCWUUWFdMb8+H9bRhBwLk9Txx6R9IBKqgSnO2bLm2kAt2pdxj2syZPTxtsj7CFKf
LRg0nRqF+OQa7XfTGa0nv6UWDGQfgH9tOUx02FKAERBCq0KftS1YqgBjKQBy8sX0
jLvMjBOUQM8bsA3I/YVFqMECgYEAzdwKH0g3V5nRW7EewOd7X+FY4kyw3WFXAWxj
kFzUz7kz1LBxdphgPJGlYM+oFnUD+Z9YU9Qll7ZXCGlL9rE/oo5OWcnUx/zHn7z7
8t6zWNbjFYYIJFZKHZZ+mnj3Mq1qTQa1lKPRrnNsLIVtHKqO0X/SRv1jZqUJWgK/
2trdGa0CgYBjRqPDjVsQ2eLg3VRfR5IZo6KggOsKW4NjrQpxeAmZR+GYHHYdCQ5O
Igr/hHFMpUXf0t/ShsJ7YEFysK+2S1sl6VdkIHTCAhmCRVsRCsAR2oJXOnYHrmLG
UQ41PkzCQnQhLMTj/0Ofs9nhGJ3P0AnvW4GgHkNVOro0cMjrYmp+cA==
-----END RSA PRIVATE KEY-----"""

public_key = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA2okOHspNjgA+2rTLbeuY
cxiP/hG8C6Sb9iwg3yiLAA4HCnpITcbWCSelbvbYGuc3EbNy4xFyf5Cbj5DHJMID
EkryOgyd2giIIIBOUBj8S63uGcnRpOBh9NFatfNwheKuzsPuVNldu6A9cNteNpXc
WyJjG2axVfmq7i6SuKr1JoWYG7xTTAvKPujSl4OtsQfO3h5NepzdfXpr28oNnzfW
ed+zclR6BcmNNo/WVfJ4xyCLSf0BCOgdTgW6PdaChd1l9VDetJZVEgC5tkyvXsfI
SI6iyrYbKR0NEBSqq4XkadEjsCs4F1RncsS4LlgniT7GlkL9Mce3b0wGLs9/7ZIX
dQIDAQAB
-----END PUBLIC KEY-----"""

payload = {
    'email': 'test@example.com',
    'sub': 'user123',
    'aud': 'tds-zeuep4ms.apps.exam.local',
    'iss': 'https://idp.exam.local',
    'exp': int(time.time()) + 3600,
}

token = jwt.encode(payload, private_key, algorithm='RS256')
print(f"Token generated, length={len(token)}")

# Test decode
decoded = jwt.decode(token, public_key, algorithms=['RS256'], issuer='https://idp.exam.local', audience='tds-zeuep4ms.apps.exam.local', leeway=30)
print(f"Decoded OK: {decoded}")

# Test with wrong audience
try:
    jwt.decode(token, public_key, algorithms=['RS256'], issuer='https://idp.exam.local', audience='wrong', leeway=30)
    print("ERROR: Should have rejected wrong audience")
except jwt.InvalidAudienceError:
    print("OK: Wrong audience rejected")

# Test with wrong issuer
try:
    jwt.decode(token, public_key, algorithms=['RS256'], issuer='https://wrong.example.com', audience='tds-zeuep4ms.apps.exam.local', leeway=30)
    print("ERROR: Should have rejected wrong issuer")
except jwt.InvalidIssuerError:
    print("OK: Wrong issuer rejected")

print("All tests passed!")
