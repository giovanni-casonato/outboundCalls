from abc import ABC, abstractmethod
from fastapi import WebSocket

class TTSProvider(ABC):
    """
    Abstract base class for TTS providers.
    All TTS implementations should inherit from this class.
    """
    def __init__(self, ws: WebSocket, stream_sid: str):
        self.ws = ws
        self.stream_sid = stream_sid
    
    @abstractmethod
    async def get_audio_from_text(self, text: str) -> bool:
        """
        Convert text to audio, encode it as base64, and send it through the websocket.
        
        Args:
            text: The text to convert to speech
            
        Returns:
            bool: Success or failure of the operation
        """
        pass