from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request, Response
from datetime import datetime, timezone
import os
from dotenv import load_dotenv

load_dotenv()

limiter = Limiter(key_func=get_remote_address)

def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> Response:
    """
    Handler personalizado para quando o rate limit é excecedido. Retorna uma resposta JSON com detalhes do erro.
    """
    if "minute" in exc.detail:
        retry_after = 60
    elif "hour" in exc.detail:
        retry_after = 3600
    elif "second" in exc.detail:
        retry_after = 1
    elif "day" in exc.detail:
        retry_after = 86400
    else:
        retry_after = 60 # Default para 1 minuto

        response = Response(content=f'{{"error": "Rate limit exceeded", "message": "Too many requests. Limit: {exc.detail}", "retry_after": {retry_after}, "timestamp": "{datetime.now(timezone.utc).isoformat()}"}}', status_code=429, media_type="application/json")

        response.headers["X-RateLimit-Limit"] = str(exc.detail)
        response.headers["X-RateLimit-Remaining"] = "0"
        response.headers["X-RateLimit-Reset"] = str(int(datetime.now(timezone.utc).timestamp()) + retry_after)
        response.headers["Retry-After"] = str(retry_after)

        RATE_LIMITS = {
            "critical": os.getenv("RATE_LIMIT_CRITICAL", "5/minute"), # Muito restritivo - Login, refresh, logout, exclusões, operações sensíveis
            "restrictive": os.getenv("RATE_LIMIT_RESTRICTIVE", "20/minute"), # Restritivo - Criações, atualizações, exclusões de dados
            "moderate": os.getenv("RATE_LIMIT_MODERATE", "100/minute"), # Moderado - Listagens, buscas por ID, auditoria
            "low": os.getenv("RATE_LIMIT_LOW", "200/minute"), # Baixo - Health checks, endpoints de sistema, documentos
            "light": os.getenv("RATE_LIMIT_LIGHT", "300/minute"), # Leve - Endpoints públicos, documentação
            "default": os.getenv("RATE_LIMIT_DEFAULT", "50/minute") # Padrão para endpoints não especificados
}
        
        def get_rate_limit(endpoint_type: str) -> str:
            return RATE_LIMITS.get(endpoint_type, RATE_LIMITS["default"])