"""
异常定义模块
"""

class AISDKException(Exception):
    """AI SDK基础异常类"""
    
    def __init__(self, message: str, error_code: str = None):
        """
        初始化异常
        
        Args:
            message: 错误消息
            error_code: 错误代码
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code
    
    def __str__(self):
        if self.error_code:
            return f"[{self.error_code}] {self.message}"
        return self.message

class ProviderException(AISDKException):
    """厂商相关异常"""
    
    def __init__(self, provider: str, message: str, error_code: str = None):
        """
        初始化厂商异常
        
        Args:
            provider: 厂商名称
            message: 错误消息
            error_code: 错误代码
        """
        super().__init__(f"厂商 {provider}: {message}", error_code)
        self.provider = provider

class ModelException(AISDKException):
    """模型相关异常"""
    
    def __init__(self, model: str, message: str, error_code: str = None):
        """
        初始化模型异常
        
        Args:
            model: 模型名称
            message: 错误消息
            error_code: 错误代码
        """
        super().__init__(f"模型 {model}: {message}", error_code)
        self.model = model

class APIException(AISDKException):
    """API调用异常"""
    
    def __init__(self, message: str, status_code: int = None, error_code: str = None):
        """
        初始化API异常
        
        Args:
            message: 错误消息
            status_code: HTTP状态码
            error_code: 错误代码
        """
        super().__init__(message, error_code)
        self.status_code = status_code

class ConfigException(AISDKException):
    """配置相关异常"""
    pass

class ValidationException(AISDKException):
    """参数验证异常"""
    pass 