import base64

encoded = "CBwQAhoeEgoyMDI0LTEyLTAxagcIARIDSkZLcgcIARIDTEFYGh4SCjIwMjQtMTItMDVqBwgBEgNMQVhyBwgBEgNKRktAAUgBcAGCAQsI____________AZgBAQ"
decoded = base64.urlsafe_b64decode(encoded + "==")
print(decoded)