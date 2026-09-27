# TradingAgents-Calv v3.0 | 教育用途，不构成投资建议
"""数据源抽象基类：所有数据源实现统一接口。
每个方法返回 dict 列表 / dict，字段与 Stock 模型对齐：
code, name, market, industry, currency, pe, pb, price
"""
from abc import ABC, abstractmethod


class DataSourceBase(ABC):
    name: str = "base"

    @abstractmethod
    def list_stocks(self) -> list[dict]:
        """返回数据源全量/推荐股票列表"""
        raise NotImplementedError

    @abstractmethod
    def get_quote(self, code: str) -> dict | None:
        """按代码查询单只股票快照，查不到返回 None"""
        raise NotImplementedError

    @abstractmethod
    def search(self, q: str, market: str | None = None) -> list[dict]:
        """按关键字（代码/名称）与可选市场过滤搜索"""
        raise NotImplementedError
