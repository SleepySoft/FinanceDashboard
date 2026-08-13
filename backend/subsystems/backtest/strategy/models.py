"""回测相关数据模型"""
from pydantic import BaseModel
from typing import Optional, List, Literal


class StrategyParam(BaseModel):
    name: str
    type: Literal['int', 'float', 'string', 'bool', 'select']
    default: Optional[str] = None
    min: Optional[float] = None
    max: Optional[float] = None
    step: Optional[float] = None
    options: Optional[List[str]] = None
    description: str = ""


class CreateStrategyReq(BaseModel):
    name: str
    description: str = ""
    notes: str = ""
    source: str
    params: List[StrategyParam] = []
    tags: List[str] = []


class BacktestRunReq(BaseModel):
    strategy_id: str
    params: dict = {}
    codes: List[str]
    start_date: str
    end_date: str
    config: Optional[dict] = None
    use_cache: bool = True
    adjust: Literal['qfq', 'hfq', 'none'] = 'qfq'


class BacktestFrameReq(BaseModel):
    strategy_id: str
    params: dict = {}
    code: str
    start_date: str
    end_date: str
    config: Optional[dict] = None
    adjust: Literal['qfq', 'hfq', 'none'] = 'qfq'
