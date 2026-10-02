"""Local worker transport, packaged as network.py in the browser ONLY."""
class ClientChannel:
    def __init__(self, unused):
        self.controls = []

    def control(self, message):
        self.controls.append(message)