"""
建筑工程地基基础计算模块

本模块提供独立基础和条形基础的承载力计算功能，符合Eurocode 2和Eurocode 7规范要求。
包含Pydantic数据验证模型，确保输入数据的完整性和正确性。

作者: AI Assistant
日期: 2026-03-13
版本: 1.0.0

依赖:
    - pydantic >= 2.0
    - Python >= 3.8
"""

from typing import Optional, Tuple, Dict, Any, Literal
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict
import math
from enum import Enum


# ============================================================================
# 枚举类型定义
# ============================================================================

class LoadType(str, Enum):
    """荷载类型枚举"""
    PERMANENT = "permanent"      # 永久荷载
    IMPOSED = "imposed"          # 可变荷载
    WIND = "wind"                # 风荷载
    SNOW = "snow"                # 雪荷载
    SEISMIC = "seismic"          # 地震荷载


class FoundationType(str, Enum):
    """基础类型枚举"""
    PAD = "pad"                  # 独立基础
    STRIP = "strip"              # 条形基础
    COMBINED = "combined"        # 联合基础
    MAT = "mat"                  # 筏板基础


class SoilType(str, Enum):
    """土壤类型枚举（用于估算内摩擦角）"""
    CLAY = "clay"                # 粘土
    SILT = "silt"                # 粉土
    SAND = "sand"                # 砂土
    GRAVEL = "gravel"            # 砾石
    ROCK = "rock"                # 岩石


class ConcreteGrade(int, Enum):
    """混凝土强度等级枚举 (N/mm²)"""
    C16 = 16
    C20 = 20
    C25 = 25
    C30 = 30
    C32 = 32
    C35 = 35
    C37 = 37
    C40 = 40
    C45 = 45
    C50 = 50
    C55 = 55


class SteelGrade(int, Enum):
    """钢筋强度等级枚举 (N/mm²)"""
    S250 = 250
    S410 = 410
    S460 = 460
    S500 = 500


class BarDiameter(int, Enum):
    """钢筋直径枚举 (mm)"""
    D8 = 8
    D10 = 10
    D12 = 12
    D16 = 16
    D20 = 20
    D25 = 25
    D32 = 32
    D40 = 40


# ============================================================================
# Pydantic 数据模型
# ============================================================================

class FoundationGeometry(BaseModel):
    """
    基础几何参数模型
    
    Attributes:
        length: 基础长度 (mm)，沿X轴方向
        width: 基础宽度 (mm)，沿Y轴方向
        thickness: 基础厚度 (mm)
        column_length: 柱长度 (mm)，沿X轴方向
        column_width: 柱宽度 (mm)，沿Y轴方向
        col_pos_xdir: 柱在X方向的位置 (mm)，从基础左边缘到柱中心的距离
        col_pos_ydir: 柱在Y方向的位置 (mm)，从基础下边缘到柱中心的距离
    """
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "length": 2400,
                "width": 2400,
                "thickness": 650,
                "column_length": 400,
                "column_width": 400,
                "col_pos_xdir": 1200,
                "col_pos_ydir": 1200
            }
        }
    )
    
    length: float = Field(..., gt=800, description="基础长度(mm)，必须大于800")
    width: float = Field(..., gt=800, description="基础宽度(mm)，必须大于800")
    thickness: float = Field(default=300, gt=100, description="基础厚度(mm)")
    column_length: float = Field(default=400, gt=100, description="柱长度(mm)")
    column_width: float = Field(default=400, gt=100, description="柱宽度(mm)")
    col_pos_xdir: Optional[float] = Field(default=None, description="柱X方向位置(mm)")
    col_pos_ydir: Optional[float] = Field(default=None, description="柱Y方向位置(mm)")
    
    @model_validator(mode='after')
    def set_default_column_positions(self):
        """设置柱位置默认值（基础中心）"""
        if self.col_pos_xdir is None:
            self.col_pos_xdir = self.length / 2
        if self.col_pos_ydir is None:
            self.col_pos_ydir = self.width / 2
        return self
    
    @field_validator('col_pos_xdir')
    @classmethod
    def validate_col_pos_xdir(cls, v, info):
        """验证柱X方向位置"""
        if v is not None:
            length = info.data.get('length')
            if length and v > length:
                raise ValueError(f"柱X方向位置({v})不能大于基础长度({length})")
        return v
    
    @field_validator('col_pos_ydir')
    @classmethod
    def validate_col_pos_ydir(cls, v, info):
        """验证柱Y方向位置"""
        if v is not None:
            width = info.data.get('width')
            if width and v > width:
                raise ValueError(f"柱Y方向位置({v})不能大于基础宽度({width})")
        return v


class StripFoundationGeometry(BaseModel):
    """
    条形基础几何参数模型
    
    Attributes:
        length: 基础长度 (mm)，沿墙方向
        width: 基础宽度 (mm)，垂直于墙方向
        thickness: 基础厚度 (mm)
        wall_width: 墙宽度 (mm)
        wall_position: 墙在宽度方向的位置 (mm)
    """
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "length": 5000,
                "width": 1200,
                "thickness": 400,
                "wall_width": 300,
                "wall_position": 600
            }
        }
    )
    
    length: float = Field(..., gt=1000, description="基础长度(mm)，必须大于1000")
    width: float = Field(..., gt=600, description="基础宽度(mm)，必须大于600")
    thickness: float = Field(default=300, gt=100, description="基础厚度(mm)")
    wall_width: float = Field(default=300, gt=100, description="墙宽度(mm)")
    wall_position: Optional[float] = Field(default=None, description="墙位置(mm)")
    
    @model_validator(mode='after')
    def set_default_wall_position(self):
        """设置墙位置默认值（基础中心）"""
        if self.wall_position is None:
            self.wall_position = self.width / 2
        return self


class FoundationLoads(BaseModel):
    """
    基础荷载参数模型
    
    Attributes:
        permanent_axial: 永久轴向荷载 (kN)，正值为压力，负值为拉力
        imposed_axial: 可变轴向荷载 (kN)
        wind_axial: 风荷载轴向分量 (kN)
        permanent_horizontal_x: X方向永久水平荷载 (kN)
        permanent_horizontal_y: Y方向永久水平荷载 (kN)
        imposed_horizontal_x: X方向可变水平荷载 (kN)
        imposed_horizontal_y: Y方向可变水平荷载 (kN)
        wind_horizontal_x: X方向风荷载 (kN)
        wind_horizontal_y: Y方向风荷载 (kN)
        permanent_moment_x: X方向永久弯矩 (kNm)
        permanent_moment_y: Y方向永久弯矩 (kNm)
        imposed_moment_x: X方向可变弯矩 (kNm)
        imposed_moment_y: Y方向可变弯矩 (kNm)
        wind_moment_x: X方向风弯矩 (kNm)
        wind_moment_y: Y方向风弯矩 (kNm)
    """
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "permanent_axial": 1000,
                "imposed_axial": 500,
                "wind_axial": 200,
                "permanent_horizontal_x": 50,
                "permanent_moment_x": 100
            }
        }
    )
    
    # 轴向荷载 (kN)
    permanent_axial: float = Field(default=0, description="永久轴向荷载(kN)")
    imposed_axial: float = Field(default=0, description="可变轴向荷载(kN)")
    wind_axial: float = Field(default=0, description="风荷载轴向分量(kN)")
    
    # 水平荷载 (kN)
    permanent_horizontal_x: float = Field(default=0, description="X方向永久水平荷载(kN)")
    permanent_horizontal_y: float = Field(default=0, description="Y方向永久水平荷载(kN)")
    imposed_horizontal_x: float = Field(default=0, description="X方向可变水平荷载(kN)")
    imposed_horizontal_y: float = Field(default=0, description="Y方向可变水平荷载(kN)")
    wind_horizontal_x: float = Field(default=0, description="X方向风荷载(kN)")
    wind_horizontal_y: float = Field(default=0, description="Y方向风荷载(kN)")
    
    # 弯矩 (kNm)
    permanent_moment_x: float = Field(default=0, description="X方向永久弯矩(kNm)")
    permanent_moment_y: float = Field(default=0, description="Y方向永久弯矩(kNm)")
    imposed_moment_x: float = Field(default=0, description="X方向可变弯矩(kNm)")
    imposed_moment_y: float = Field(default=0, description="Y方向可变弯矩(kNm)")
    wind_moment_x: float = Field(default=0, description="X方向风弯矩(kNm)")
    wind_moment_y: float = Field(default=0, description="Y方向风弯矩(kNm)")


class SoilParameters(BaseModel):
    """
    土壤参数模型
    
    Attributes:
        bearing_capacity: 地基承载力特征值 (kN/m²)
        soil_unit_weight: 土体重度 (kN/m³)
        soil_depth_above: 基础上覆土深度 (mm)
        friction_angle: 土体内摩擦角 (度)
        cohesion: 粘聚力 (kN/m²)
        soil_type: 土壤类型
    """
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "bearing_capacity": 200,
                "soil_unit_weight": 18,
                "soil_depth_above": 500,
                "soil_type": "sand"
            }
        }
    )
    
    bearing_capacity: float = Field(default=150, gt=0, description="地基承载力(kN/m²)")
    soil_unit_weight: float = Field(default=18, gt=0, description="土体重度(kN/m³)")
    soil_depth_above: float = Field(default=500, ge=0, description="上覆土深度(mm)")
    friction_angle: Optional[float] = Field(default=None, description="内摩擦角(度)")
    cohesion: float = Field(default=0, ge=0, description="粘聚力(kN/m²)")
    soil_type: SoilType = Field(default=SoilType.SAND, description="土壤类型")
    
    @model_validator(mode='after')
    def set_friction_angle(self):
        """根据土壤类型设置默认内摩擦角"""
        if self.friction_angle is None:
            friction_angles = {
                SoilType.CLAY: 20,
                SoilType.SILT: 25,
                SoilType.SAND: 30,
                SoilType.GRAVEL: 35,
                SoilType.ROCK: 40
            }
            self.friction_angle = friction_angles.get(self.soil_type, 30)
        return self


class ConcreteParameters(BaseModel):
    """
    混凝土参数模型
    
    Attributes:
        fck: 混凝土特征抗压强度 (N/mm²)
        fyk: 钢筋特征屈服强度 (N/mm²)
        concrete_cover: 混凝土保护层厚度 (mm)
        bar_diameter_x: X方向钢筋直径 (mm)
        bar_diameter_y: Y方向钢筋直径 (mm)
        concrete_unit_weight: 混凝土重度 (kN/m³)
    """
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "fck": 30,
                "fyk": 460,
                "concrete_cover": 40,
                "bar_diameter_x": 16,
                "bar_diameter_y": 16
            }
        }
    )
    
    fck: ConcreteGrade = Field(default=ConcreteGrade.C25, description="混凝土强度等级")
    fyk: SteelGrade = Field(default=SteelGrade.S460, description="钢筋强度等级")
    concrete_cover: float = Field(default=30, ge=20, description="保护层厚度(mm)")
    bar_diameter_x: BarDiameter = Field(default=BarDiameter.D16, description="X方向钢筋直径")
    bar_diameter_y: BarDiameter = Field(default=BarDiameter.D16, description="Y方向钢筋直径")
    concrete_unit_weight: float = Field(default=24, description="混凝土重度(kN/m³)")


class LimitStateFactors(BaseModel):
    """
    极限状态分项系数模型
    
    根据Eurocode 0和Eurocode 1规范
    
    Attributes:
        gamma_g: 永久荷载分项系数
        gamma_q: 可变荷载分项系数
        gamma_w: 风荷载分项系数
        gamma_c: 混凝土材料分项系数
        gamma_s: 钢筋材料分项系数
    """
    gamma_g: float = Field(default=1.35, description="永久荷载分项系数")
    gamma_q: float = Field(default=1.5, description="可变荷载分项系数")
    gamma_w: float = Field(default=1.5, description="风荷载分项系数")
    gamma_c: float = Field(default=1.5, description="混凝土材料分项系数")
    gamma_s: float = Field(default=1.15, description="钢筋材料分项系数")


class BearingPressureResult(BaseModel):
    """地基压力计算结果模型"""
    model_config = ConfigDict(frozen=True)
    
    q1: float = Field(..., description="左下角地基压力(kN/m²)")
    q2: float = Field(..., description="左上角地基压力(kN/m²)")
    q3: float = Field(..., description="右下角地基压力(kN/m²)")
    q4: float = Field(..., description="右上角地基压力(kN/m²)")
    q_max: float = Field(..., description="最大地基压力(kN/m²)")
    q_min: float = Field(..., description="最小地基压力(kN/m²)")
    q_avg: float = Field(..., description="平均地基压力(kN/m²)")
    eccentricity_x: float = Field(..., description="X方向偏心距(mm)")
    eccentricity_y: float = Field(..., description="Y方向偏心距(mm)")
    status: str = Field(..., description="验算状态")


class ReinforcementResult(BaseModel):
    """配筋计算结果模型"""
    model_config = ConfigDict(frozen=True)
    
    area_required: float = Field(..., description="所需钢筋面积(mm²/m)")
    area_provided: float = Field(..., description="实际配筋面积(mm²/m)")
    bar_diameter: int = Field(..., description="钢筋直径(mm)")
    bar_spacing: float = Field(..., description="钢筋间距(mm)")
    steel_grade: str = Field(..., description="钢筋等级")
    status: str = Field(..., description="验算状态")
    compression_reinforcement_required: bool = Field(default=False, description="是否需要受压钢筋")


class ShearCheckResult(BaseModel):
    """抗剪验算结果模型"""
    model_config = ConfigDict(frozen=True)
    
    design_shear_force: float = Field(..., description="设计剪力(kN)")
    shear_resistance: float = Field(..., description="抗剪承载力(kN)")
    shear_stress: float = Field(..., description="剪应力(N/mm²)")
    status: str = Field(..., description="验算状态")


class PunchingShearResult(BaseModel):
    """冲切验算结果模型"""
    model_config = ConfigDict(frozen=True)
    
    column_face_status: str = Field(..., description="柱面冲切验算状态")
    one_d_status: str = Field(..., description="1d处冲切验算状态")
    two_d_status: str = Field(..., description="2d处冲切验算状态")
    vrd_max: float = Field(..., description="最大抗冲切承载力(N/mm²)")
    ved_column_face: float = Field(..., description="柱面设计冲切应力(N/mm²)")
    ved_1d: float = Field(..., description="1d处设计冲切应力(N/mm²)")
    ved_2d: float = Field(..., description="2d处设计冲切应力(N/mm²)")


class SlidingResult(BaseModel):
    """抗滑移验算结果模型"""
    model_config = ConfigDict(frozen=True)
    
    horizontal_force: float = Field(..., description="水平作用力(kN)")
    sliding_resistance: float = Field(..., description="抗滑移承载力(kN)")
    friction_angle: float = Field(..., description="设计摩擦角(度)")
    status: str = Field(..., description="验算状态")


# ============================================================================
# 独立基础计算类
# ============================================================================

class PadFoundationCalculator:
    """
    独立基础（柱下扩展基础）承载力计算类
    
    本类提供独立基础的完整计算功能，包括：
    - 地基承载力验算（SLS和ULS）
    - 基底压力计算
    - 配筋计算
    - 抗剪验算
    - 冲切验算
    - 抗滑移验算
    
    符合Eurocode 2和Eurocode 7规范要求。
    
    Example:
        >>> geometry = FoundationGeometry(length=2400, width=2400, thickness=650)
        >>> loads = FoundationLoads(permanent_axial=1000, imposed_axial=500)
        >>> soil = SoilParameters(bearing_capacity=200)
        >>> concrete = ConcreteParameters(fck=ConcreteGrade.C30)
        >>> calculator = PadFoundationCalculator(geometry, loads, soil, concrete)
        >>> result = calculator.calculate_bearing_pressure_sls()
        >>> print(result)
    """
    
    def __init__(
        self,
        geometry: FoundationGeometry,
        loads: FoundationLoads,
        soil: SoilParameters,
        concrete: ConcreteParameters,
        factors: Optional[LimitStateFactors] = None
    ):
        """
        初始化独立基础计算器
        
        Args:
            geometry: 基础几何参数
            loads: 荷载参数
            soil: 土壤参数
            concrete: 混凝土参数
            factors: 极限状态分项系数（可选，使用默认值）
        """
        self.geometry = geometry
        self.loads = loads
        self.soil = soil
        self.concrete = concrete
        self.factors = factors or LimitStateFactors()
        
        # 转换为计算单位（米）
        self.L = geometry.length / 1000  # 基础长度 (m)
        self.B = geometry.width / 1000   # 基础宽度 (m)
        self.h = geometry.thickness / 1000  # 基础厚度 (m)
        self.cx = geometry.column_length / 1000  # 柱长度 (m)
        self.cy = geometry.column_width / 1000   # 柱宽度 (m)
        self.col_x = (geometry.col_pos_xdir or geometry.length / 2) / 1000  # 柱X位置 (m)
        self.col_y = (geometry.col_pos_ydir or geometry.width / 2) / 1000  # 柱Y位置 (m)
        
        # 计算有效高度
        self.dx = self.h - (concrete.concrete_cover / 1000) - (concrete.bar_diameter_x.value / 2000)
        self.dy = self.h - (concrete.concrete_cover / 1000) - (concrete.bar_diameter_x.value / 1000) - (concrete.bar_diameter_y.value / 2000)
        self.d_avg = (self.dx + self.dy) / 2
    
    def area(self) -> float:
        """计算基础底面积 (m²)"""
        return self.L * self.B
    
    def section_modulus_x(self) -> float:
        """计算X方向截面模量 (m³)"""
        return self.B * self.L ** 2 / 6
    
    def section_modulus_y(self) -> float:
        """计算Y方向截面模量 (m³)"""
        return self.L * self.B ** 2 / 6
    
    def foundation_self_weight(self) -> float:
        """计算基础自重 (kN)"""
        return self.area() * self.h * self.concrete.concrete_unit_weight
    
    def soil_weight_above(self) -> float:
        """计算基础上覆土重 (kN)"""
        soil_depth = self.soil.soil_depth_above / 1000
        return self.area() * soil_depth * self.soil.soil_unit_weight
    
    def total_vertical_load_sls(self) -> float:
        """
        计算使用极限状态(SLS)下的总竖向荷载 (kN)
        
        SLS组合: 1.0*G_k + 1.0*Q_k + 1.0*W_k
        """
        column_load = (
            self.loads.permanent_axial +
            self.loads.imposed_axial +
            self.loads.wind_axial
        )
        return column_load + self.foundation_self_weight() + self.soil_weight_above()
    
    def total_vertical_load_uls(self) -> float:
        """
        计算承载能力极限状态(ULS)下的总竖向荷载 (kN)
        
        ULS组合: 1.35*G_k + 1.5*Q_k + 1.5*W_k
        """
        column_load = (
            self.factors.gamma_g * self.loads.permanent_axial +
            self.factors.gamma_q * self.loads.imposed_axial +
            self.factors.gamma_w * self.loads.wind_axial
        )
        foundation_load = self.factors.gamma_g * (self.foundation_self_weight() + self.soil_weight_above())
        return column_load + foundation_load
    
    def total_moment_x_sls(self) -> float:
        """计算SLS下绕X轴的总弯矩 (kNm)"""
        # 荷载产生的弯矩
        moment_from_loads = (
            self.loads.permanent_axial * self.col_x +
            self.loads.imposed_axial * self.col_x +
            self.loads.wind_axial * self.col_x +
            self.loads.permanent_moment_x +
            self.loads.imposed_moment_x +
            self.loads.wind_moment_x +
            self.loads.permanent_horizontal_x * self.h +
            self.loads.imposed_horizontal_x * self.h +
            self.loads.wind_horizontal_x * self.h
        )
        # 基础自重和土重产生的弯矩（作用在中心）
        moment_from_weight = (self.foundation_self_weight() + self.soil_weight_above()) * self.L / 2
        return moment_from_loads + moment_from_weight
    
    def total_moment_y_sls(self) -> float:
        """计算SLS下绕Y轴的总弯矩 (kNm)"""
        moment_from_loads = (
            self.loads.permanent_axial * self.col_y +
            self.loads.imposed_axial * self.col_y +
            self.loads.wind_axial * self.col_y +
            self.loads.permanent_moment_y +
            self.loads.imposed_moment_y +
            self.loads.wind_moment_y +
            self.loads.permanent_horizontal_y * self.h +
            self.loads.imposed_horizontal_y * self.h +
            self.loads.wind_horizontal_y * self.h
        )
        moment_from_weight = (self.foundation_self_weight() + self.soil_weight_above()) * self.B / 2
        return moment_from_loads + moment_from_weight
    
    def total_moment_x_uls(self) -> float:
        """计算ULS下绕X轴的总弯矩 (kNm)"""
        moment_from_loads = (
            self.factors.gamma_g * self.loads.permanent_axial * self.col_x +
            self.factors.gamma_q * self.loads.imposed_axial * self.col_x +
            self.factors.gamma_w * self.loads.wind_axial * self.col_x +
            self.factors.gamma_g * self.loads.permanent_moment_x +
            self.factors.gamma_q * self.loads.imposed_moment_x +
            self.factors.gamma_w * self.loads.wind_moment_x +
            self.factors.gamma_g * self.loads.permanent_horizontal_x * self.h +
            self.factors.gamma_q * self.loads.imposed_horizontal_x * self.h +
            self.factors.gamma_w * self.loads.wind_horizontal_x * self.h
        )
        moment_from_weight = self.factors.gamma_g * (self.foundation_self_weight() + self.soil_weight_above()) * self.L / 2
        return moment_from_loads + moment_from_weight
    
    def total_moment_y_uls(self) -> float:
        """计算ULS下绕Y轴的总弯矩 (kNm)"""
        moment_from_loads = (
            self.factors.gamma_g * self.loads.permanent_axial * self.col_y +
            self.factors.gamma_q * self.loads.imposed_axial * self.col_y +
            self.factors.gamma_w * self.loads.wind_axial * self.col_y +
            self.factors.gamma_g * self.loads.permanent_moment_y +
            self.factors.gamma_q * self.loads.imposed_moment_y +
            self.factors.gamma_w * self.loads.wind_moment_y +
            self.factors.gamma_g * self.loads.permanent_horizontal_y * self.h +
            self.factors.gamma_q * self.loads.imposed_horizontal_y * self.h +
            self.factors.gamma_w * self.loads.wind_horizontal_y * self.h
        )
        moment_from_weight = self.factors.gamma_g * (self.foundation_self_weight() + self.soil_weight_above()) * self.B / 2
        return moment_from_loads + moment_from_weight
    
    def eccentricity_x_sls(self) -> float:
        """计算SLS下X方向偏心距 (mm)"""
        ex = (self.total_moment_x_sls() / self.total_vertical_load_sls()) - (self.L / 2)
        return ex * 1000
    
    def eccentricity_y_sls(self) -> float:
        """计算SLS下Y方向偏心距 (mm)"""
        ey = (self.total_moment_y_sls() / self.total_vertical_load_sls()) - (self.B / 2)
        return ey * 1000
    
    def eccentricity_x_uls(self) -> float:
        """计算ULS下X方向偏心距 (mm)"""
        ex = (self.total_moment_x_uls() / self.total_vertical_load_uls()) - (self.L / 2)
        return ex * 1000
    
    def eccentricity_y_uls(self) -> float:
        """计算ULS下Y方向偏心距 (mm)"""
        ey = (self.total_moment_y_uls() / self.total_vertical_load_uls()) - (self.B / 2)
        return ey * 1000
    
    def calculate_bearing_pressure_sls(self) -> BearingPressureResult:
        """
        计算使用极限状态(SLS)下的地基压力
        
        使用公式: q = N/A ± Mx/Zx ± My/Zy
        
        Returns:
            BearingPressureResult: 地基压力计算结果
        """
        N = self.total_vertical_load_sls()
        Mx = self.total_moment_x_sls()
        My = self.total_moment_y_sls()
        
        A = self.area()
        Zx = self.section_modulus_x()
        Zy = self.section_modulus_y()
        
        # 计算四个角点的压力
        q_avg = N / A
        qx = abs(Mx) / Zx if Zx > 0 else 0
        qy = abs(My) / Zy if Zy > 0 else 0
        
        # 四个角点压力 (kN/m²)
        q1 = q_avg - qx - qy  # 左下
        q2 = q_avg - qx + qy  # 左上
        q3 = q_avg + qx - qy  # 右下
        q4 = q_avg + qx + qy  # 右上
        
        q_max = max(q1, q2, q3, q4)
        q_min = min(q1, q2, q3, q4)
        
        # 验算状态
        if q_max <= self.soil.bearing_capacity and q_min >= 0:
            status = "PASS - 地基承载力满足要求"
        elif q_max > self.soil.bearing_capacity:
            status = "FAIL - 最大地基压力超过承载力"
        else:
            status = "WARNING - 出现拉应力，基础可能脱空"
        
        return BearingPressureResult(
            q1=round(q1, 3),
            q2=round(q2, 3),
            q3=round(q3, 3),
            q4=round(q4, 3),
            q_max=round(q_max, 3),
            q_min=round(q_min, 3),
            q_avg=round(q_avg, 3),
            eccentricity_x=round(self.eccentricity_x_sls(), 3),
            eccentricity_y=round(self.eccentricity_y_sls(), 3),
            status=status
        )
    
    def calculate_bearing_pressure_uls(self) -> BearingPressureResult:
        """
        计算承载能力极限状态(ULS)下的地基压力
        
        Returns:
            BearingPressureResult: 地基压力计算结果
        """
        N = self.total_vertical_load_uls()
        Mx = self.total_moment_x_uls()
        My = self.total_moment_y_uls()
        
        A = self.area()
        Zx = self.section_modulus_x()
        Zy = self.section_modulus_y()
        
        q_avg = N / A
        qx = abs(Mx) / Zx if Zx > 0 else 0
        qy = abs(My) / Zy if Zy > 0 else 0
        
        q1 = q_avg - qx - qy
        q2 = q_avg - qx + qy
        q3 = q_avg + qx - qy
        q4 = q_avg + qx + qy
        
        q_max = max(q1, q2, q3, q4)
        q_min = min(q1, q2, q3, q4)
        
        # ULS下允许承载力可提高
        allowable_uls = self.soil.bearing_capacity * 1.5
        
        if q_max <= allowable_uls and q_min >= 0:
            status = "PASS - ULS地基承载力满足要求"
        elif q_max > allowable_uls:
            status = "FAIL - ULS最大地基压力超过承载力"
        else:
            status = "WARNING - 出现拉应力"
        
        return BearingPressureResult(
            q1=round(q1, 3),
            q2=round(q2, 3),
            q3=round(q3, 3),
            q4=round(q4, 3),
            q_max=round(q_max, 3),
            q_min=round(q_min, 3),
            q_avg=round(q_avg, 3),
            eccentricity_x=round(self.eccentricity_x_uls(), 3),
            eccentricity_y=round(self.eccentricity_y_uls(), 3),
            status=status
        )
    
    def calculate_reinforcement_x(self) -> ReinforcementResult:
        """
        计算X方向配筋
        
        根据Eurocode 2规范计算受弯钢筋面积
        
        Returns:
            ReinforcementResult: 配筋计算结果
        """
        # 计算设计弯矩（柱边处）
        # 简化计算：假设基底压力均匀分布
        q_uls = self.total_vertical_load_uls() / self.area()
        
        # 悬臂长度
        a = min(self.col_x - self.cx/2, self.L - self.col_x - self.cx/2)
        
        # 设计弯矩 (kNm/m)
        M_ed = q_uls * a ** 2 / 2
        
        # 计算钢筋面积 (Eurocode 2)
        fck = self.concrete.fck.value
        fyk = self.concrete.fyk.value
        d = self.dx * 1000  # 转换为mm
        b = 1000  # 每米宽度
        
        # 计算k值
        k = (M_ed * 1e6) / (fck * b * d ** 2)
        
        # 检查是否需要受压钢筋
        compression_required = k > 0.167
        
        if compression_required:
            # 简化为双筋截面计算
            k = 0.167
        
        # 计算内力臂
        la = 0.5 + math.sqrt(0.25 - 0.882 * k)
        if la > 0.95:
            la = 0.95
        
        # 计算钢筋面积
        A_s = (M_ed * 1e6) / (0.87 * fyk * la * d)
        
        # 计算最小配筋率
        A_s_min = max(
            0.078 * (fck ** (2/3)) / fyk * b * d,
            0.0013 * b * d
        )
        
        # 取最大值
        A_s_req = max(A_s, A_s_min)
        
        # 选择钢筋
        bar_dia = self.concrete.bar_diameter_x.value
        bar_area = math.pi * bar_dia ** 2 / 4
        spacing = min(1000 * bar_area / A_s_req, 250)
        spacing = int(spacing / 25) * 25  # 取整到25mm
        
        A_s_prov = 1000 * bar_area / spacing
        
        # 钢筋等级标签
        steel_labels = {250: "R", 410: "Y", 460: "T", 500: "H"}
        steel_label = steel_labels.get(fyk, "T")
        
        status = "PASS" if A_s_prov >= A_s_req else "FAIL"
        
        return ReinforcementResult(
            area_required=round(A_s_req, 2),
            area_provided=round(A_s_prov, 2),
            bar_diameter=bar_dia,
            bar_spacing=spacing,
            steel_grade=steel_label,
            status=status,
            compression_reinforcement_required=compression_required
        )
    
    def calculate_reinforcement_y(self) -> ReinforcementResult:
        """
        计算Y方向配筋
        
        Returns:
            ReinforcementResult: 配筋计算结果
        """
        q_uls = self.total_vertical_load_uls() / self.area()
        a = min(self.col_y - self.cy/2, self.B - self.col_y - self.cy/2)
        M_ed = q_uls * a ** 2 / 2
        
        fck = self.concrete.fck.value
        fyk = self.concrete.fyk.value
        d = self.dy * 1000
        b = 1000
        
        k = (M_ed * 1e6) / (fck * b * d ** 2)
        compression_required = k > 0.167
        
        if compression_required:
            k = 0.167
        
        la = 0.5 + math.sqrt(0.25 - 0.882 * k)
        if la > 0.95:
            la = 0.95
        
        A_s = (M_ed * 1e6) / (0.87 * fyk * la * d)
        
        A_s_min = max(
            0.078 * (fck ** (2/3)) / fyk * b * d,
            0.0013 * b * d
        )
        
        A_s_req = max(A_s, A_s_min)
        
        bar_dia = self.concrete.bar_diameter_y.value
        bar_area = math.pi * bar_dia ** 2 / 4
        spacing = min(1000 * bar_area / A_s_req, 250)
        spacing = int(spacing / 25) * 25
        
        A_s_prov = 1000 * bar_area / spacing
        
        steel_labels = {250: "R", 410: "Y", 460: "T", 500: "H"}
        steel_label = steel_labels.get(fyk, "T")
        
        status = "PASS" if A_s_prov >= A_s_req else "FAIL"
        
        return ReinforcementResult(
            area_required=round(A_s_req, 2),
            area_provided=round(A_s_prov, 2),
            bar_diameter=bar_dia,
            bar_spacing=spacing,
            steel_grade=steel_label,
            status=status,
            compression_reinforcement_required=compression_required
        )
    
    def check_punching_shear(self) -> PunchingShearResult:
        """
        冲切验算
        
        根据Eurocode 2第6.4节进行冲切验算
        
        Returns:
            PunchingShearResult: 冲切验算结果
        """
        fck = self.concrete.fck.value
        
        # 设计冲切力
        V_ed = self.total_vertical_load_uls() - self.foundation_self_weight() * 0.35
        
        # 柱周长
        u_0 = 2 * (self.cx + self.cy)
        
        # 最大冲切应力 (Eurocode 2 Eq. 6.53)
        v_rd_max = 0.5 * 0.6 * (1 - fck / 250) * fck / self.factors.gamma_c
        
        # 柱面处冲切应力
        v_ed_col = V_ed * 1000 / (u_0 * self.d_avg * 1000)
        
        col_status = "PASS" if v_rd_max > v_ed_col else "FAIL"
        
        # 1d处冲切验算
        u_1 = u_0 + 2 * math.pi * self.d_avg
        v_ed_1d = V_ed * 1000 / (u_1 * self.d_avg * 1000)
        
        # 计算混凝土抗冲切承载力
        k = min(1 + math.sqrt(200 / (self.d_avg * 1000)), 2)
        
        # 配筋率
        rho_x = self.calculate_reinforcement_x().area_provided / (1000 * self.dx * 1000)
        rho_y = self.calculate_reinforcement_y().area_provided / (1000 * self.dy * 1000)
        rho_l = min(math.sqrt(rho_x * rho_y), 0.02)
        
        v_rd_c = max(
            0.12 * k * (100 * rho_l * fck) ** (1/3),
            0.035 * k ** 1.5 * math.sqrt(fck)
        )
        
        # 1d处抗冲切承载力 (Eurocode 2 Eq. 6.50)
        v_rd_1d = 2 * v_rd_c
        
        one_d_status = "PASS" if v_rd_1d > v_ed_1d else "FAIL"
        
        # 2d处冲切验算
        u_2 = u_0 + 4 * math.pi * self.d_avg
        v_ed_2d = V_ed * 1000 / (u_2 * self.d_avg * 1000)
        v_rd_2d = v_rd_c
        
        two_d_status = "PASS" if v_rd_2d > v_ed_2d else "FAIL"
        
        return PunchingShearResult(
            column_face_status=col_status,
            one_d_status=one_d_status,
            two_d_status=two_d_status,
            vrd_max=round(v_rd_max, 3),
            ved_column_face=round(v_ed_col, 3),
            ved_1d=round(v_ed_1d, 3),
            ved_2d=round(v_ed_2d, 3)
        )
    
    def check_sliding(self) -> SlidingResult:
        """
        抗滑移验算
        
        根据Eurocode 7第6.5.3节进行抗滑移验算
        
        Returns:
            SlidingResult: 抗滑移验算结果
        """
        # 计算水平力
        H_x = (
            self.factors.gamma_g * self.loads.permanent_horizontal_x +
            self.factors.gamma_q * self.loads.imposed_horizontal_x +
            self.factors.gamma_w * self.loads.wind_horizontal_x
        )
        H_y = (
            self.factors.gamma_g * self.loads.permanent_horizontal_y +
            self.factors.gamma_q * self.loads.imposed_horizontal_y +
            self.factors.gamma_w * self.loads.wind_horizontal_y
        )
        
        H_total = math.sqrt(H_x ** 2 + H_y ** 2)
        
        # 竖向力（用于计算摩擦力）
        V = self.total_vertical_load_uls()
        
        # 设计摩擦角 - 确保friction_angle有值
        friction_angle = self.soil.friction_angle or 30  # 默认30度
        phi_d = math.radians(friction_angle) / self.factors.gamma_g
        
        # 抗滑移承载力
        R_d = V * math.tan(phi_d)
        
        status = "PASS" if R_d > H_total else "FAIL"
        
        return SlidingResult(
            horizontal_force=round(H_total, 3),
            sliding_resistance=round(R_d, 3),
            friction_angle=round(math.degrees(phi_d), 2),
            status=status
        )
    
    def run_full_analysis(self) -> Dict[str, Any]:
        """
        运行完整分析
        
        执行所有验算并返回完整结果
        
        Returns:
            Dict: 包含所有验算结果的字典
        """
        return {
            "基础信息": {
                "基础面积": f"{self.area():.3f} m²",
                "基础长度": f"{self.L:.3f} m",
                "基础宽度": f"{self.B:.3f} m",
                "基础厚度": f"{self.h:.3f} m",
                "有效高度dx": f"{self.dx:.3f} m",
                "有效高度dy": f"{self.dy:.3f} m"
            },
            "SLS地基压力": self.calculate_bearing_pressure_sls().model_dump(),
            "ULS地基压力": self.calculate_bearing_pressure_uls().model_dump(),
            "X方向配筋": self.calculate_reinforcement_x().model_dump(),
            "Y方向配筋": self.calculate_reinforcement_y().model_dump(),
            "冲切验算": self.check_punching_shear().model_dump(),
            "抗滑移验算": self.check_sliding().model_dump()
        }


# ============================================================================
# 条形基础计算类
# ============================================================================

class StripFoundationCalculator:
    """
    条形基础（墙下扩展基础）承载力计算类
    
    本类提供条形基础的完整计算功能，适用于墙下条形基础设计。
    计算按每延米进行。
    
    Example:
        >>> geometry = StripFoundationGeometry(length=5000, width=1200, thickness=400)
        >>> loads = FoundationLoads(permanent_axial=150, imposed_axial=75)
        >>> soil = SoilParameters(bearing_capacity=150)
        >>> concrete = ConcreteParameters(fck=ConcreteGrade.C25)
        >>> calculator = StripFoundationCalculator(geometry, loads, soil, concrete)
        >>> result = calculator.calculate_bearing_pressure_sls()
    """
    
    def __init__(
        self,
        geometry: StripFoundationGeometry,
        loads: FoundationLoads,
        soil: SoilParameters,
        concrete: ConcreteParameters,
        factors: Optional[LimitStateFactors] = None
    ):
        """
        初始化条形基础计算器
        
        Args:
            geometry: 条形基础几何参数
            loads: 荷载参数（按每延米计）
            soil: 土壤参数
            concrete: 混凝土参数
            factors: 极限状态分项系数
        """
        self.geometry = geometry
        self.loads = loads
        self.soil = soil
        self.concrete = concrete
        self.factors = factors or LimitStateFactors()
        
        # 转换为计算单位（米）
        self.L = geometry.length / 1000  # 基础长度 (m)
        self.B = geometry.width / 1000   # 基础宽度 (m)
        self.h = geometry.thickness / 1000  # 基础厚度 (m)
        self.wall_w = geometry.wall_width / 1000  # 墙宽度 (m)
        self.wall_pos = (geometry.wall_position or geometry.width / 2) / 1000  # 墙位置 (m)
        
        # 计算有效高度
        self.d = self.h - (concrete.concrete_cover / 1000) - (concrete.bar_diameter_x.value / 2000)
    
    def area_per_meter(self) -> float:
        """计算每延米基础面积 (m²/m)"""
        return self.B
    
    def foundation_self_weight_per_meter(self) -> float:
        """计算每延米基础自重 (kN/m)"""
        return self.B * self.h * self.concrete.concrete_unit_weight
    
    def soil_weight_above_per_meter(self) -> float:
        """计算每延米上覆土重 (kN/m)"""
        soil_depth = self.soil.soil_depth_above / 1000
        return self.B * soil_depth * self.soil.soil_unit_weight
    
    def total_vertical_load_sls_per_meter(self) -> float:
        """计算SLS下每延米总竖向荷载 (kN/m)"""
        column_load = (
            self.loads.permanent_axial +
            self.loads.imposed_axial +
            self.loads.wind_axial
        )
        return column_load + self.foundation_self_weight_per_meter() + self.soil_weight_above_per_meter()
    
    def total_vertical_load_uls_per_meter(self) -> float:
        """计算ULS下每延米总竖向荷载 (kN/m)"""
        column_load = (
            self.factors.gamma_g * self.loads.permanent_axial +
            self.factors.gamma_q * self.loads.imposed_axial +
            self.factors.gamma_w * self.loads.wind_axial
        )
        foundation_load = self.factors.gamma_g * (self.foundation_self_weight_per_meter() + self.soil_weight_above_per_meter())
        return column_load + foundation_load
    
    def total_moment_sls_per_meter(self) -> float:
        """计算SLS下每延米总弯矩 (kNm/m)"""
        moment_from_loads = (
            self.loads.permanent_axial * self.wall_pos +
            self.loads.imposed_axial * self.wall_pos +
            self.loads.wind_axial * self.wall_pos +
            self.loads.permanent_moment_x +
            self.loads.imposed_moment_x +
            self.loads.wind_moment_x
        )
        moment_from_weight = (self.foundation_self_weight_per_meter() + self.soil_weight_above_per_meter()) * self.B / 2
        return moment_from_loads + moment_from_weight
    
    def total_moment_uls_per_meter(self) -> float:
        """计算ULS下每延米总弯矩 (kNm/m)"""
        moment_from_loads = (
            self.factors.gamma_g * self.loads.permanent_axial * self.wall_pos +
            self.factors.gamma_q * self.loads.imposed_axial * self.wall_pos +
            self.factors.gamma_w * self.loads.wind_axial * self.wall_pos +
            self.factors.gamma_g * self.loads.permanent_moment_x +
            self.factors.gamma_q * self.loads.imposed_moment_x +
            self.factors.gamma_w * self.loads.wind_moment_x
        )
        moment_from_weight = self.factors.gamma_g * (self.foundation_self_weight_per_meter() + self.soil_weight_above_per_meter()) * self.B / 2
        return moment_from_loads + moment_from_weight
    
    def eccentricity_sls(self) -> float:
        """计算SLS下偏心距 (mm)"""
        e = (self.total_moment_sls_per_meter() / self.total_vertical_load_sls_per_meter()) - (self.B / 2)
        return e * 1000
    
    def eccentricity_uls(self) -> float:
        """计算ULS下偏心距 (mm)"""
        e = (self.total_moment_uls_per_meter() / self.total_vertical_load_uls_per_meter()) - (self.B / 2)
        return e * 1000
    
    def calculate_bearing_pressure_sls(self) -> Dict[str, float]:
        """
        计算SLS下的地基压力
        
        Returns:
            Dict: 地基压力结果
        """
        N = self.total_vertical_load_sls_per_meter()
        M = self.total_moment_sls_per_meter()
        
        A = self.B
        W = self.B ** 2 / 6
        
        q_avg = N / A
        q_moment = abs(M) / W if W > 0 else 0
        
        q_max = q_avg + q_moment
        q_min = q_avg - q_moment
        
        if q_max <= self.soil.bearing_capacity and q_min >= 0:
            status = "PASS - 地基承载力满足要求"
        elif q_max > self.soil.bearing_capacity:
            status = "FAIL - 最大地基压力超过承载力"
        else:
            status = "WARNING - 出现拉应力"
        
        return {
            "q_max": round(q_max, 3),
            "q_min": round(q_min, 3),
            "q_avg": round(q_avg, 3),
            "eccentricity": round(self.eccentricity_sls(), 3),
            "status": status
        }
    
    def calculate_bearing_pressure_uls(self) -> Dict[str, float]:
        """计算ULS下的地基压力"""
        N = self.total_vertical_load_uls_per_meter()
        M = self.total_moment_uls_per_meter()
        
        A = self.B
        W = self.B ** 2 / 6
        
        q_avg = N / A
        q_moment = abs(M) / W if W > 0 else 0
        
        q_max = q_avg + q_moment
        q_min = q_avg - q_moment
        
        allowable_uls = self.soil.bearing_capacity * 1.5
        
        if q_max <= allowable_uls and q_min >= 0:
            status = "PASS - ULS地基承载力满足要求"
        elif q_max > allowable_uls:
            status = "FAIL - ULS最大地基压力超过承载力"
        else:
            status = "WARNING - 出现拉应力"
        
        return {
            "q_max": round(q_max, 3),
            "q_min": round(q_min, 3),
            "q_avg": round(q_avg, 3),
            "eccentricity": round(self.eccentricity_uls(), 3),
            "status": status
        }
    
    def calculate_reinforcement(self) -> ReinforcementResult:
        """
        计算横向配筋
        
        Returns:
            ReinforcementResult: 配筋计算结果
        """
        q_uls = self.total_vertical_load_uls_per_meter() / self.B
        
        # 悬臂长度（取较大值）
        a = max(self.wall_pos - self.wall_w/2, self.B - self.wall_pos - self.wall_w/2)
        
        # 设计弯矩
        M_ed = q_uls * a ** 2 / 2
        
        fck = self.concrete.fck.value
        fyk = self.concrete.fyk.value
        d = self.d * 1000
        b = 1000
        
        k = (M_ed * 1e6) / (fck * b * d ** 2)
        compression_required = k > 0.167
        
        if compression_required:
            k = 0.167
        
        la = 0.5 + math.sqrt(0.25 - 0.882 * k)
        if la > 0.95:
            la = 0.95
        
        A_s = (M_ed * 1e6) / (0.87 * fyk * la * d)
        
        A_s_min = max(
            0.078 * (fck ** (2/3)) / fyk * b * d,
            0.0013 * b * d
        )
        
        A_s_req = max(A_s, A_s_min)
        
        bar_dia = self.concrete.bar_diameter_x.value
        bar_area = math.pi * bar_dia ** 2 / 4
        spacing = min(1000 * bar_area / A_s_req, 250)
        spacing = int(spacing / 25) * 25
        
        A_s_prov = 1000 * bar_area / spacing
        
        steel_labels = {250: "R", 410: "Y", 460: "T", 500: "H"}
        steel_label = steel_labels.get(fyk, "T")
        
        status = "PASS" if A_s_prov >= A_s_req else "FAIL"
        
        return ReinforcementResult(
            area_required=round(A_s_req, 2),
            area_provided=round(A_s_prov, 2),
            bar_diameter=bar_dia,
            bar_spacing=spacing,
            steel_grade=steel_label,
            status=status,
            compression_reinforcement_required=compression_required
        )
    
    def check_shear(self) -> ShearCheckResult:
        """
        抗剪验算
        
        Returns:
            ShearCheckResult: 抗剪验算结果
        """
        q_uls = self.total_vertical_load_uls_per_meter() / self.B
        
        # 验算位置：距墙边1d处
        a = max(self.wall_pos - self.wall_w/2, self.B - self.wall_pos - self.wall_w/2)
        x = a - self.d
        
        if x < 0:
            x = a / 2
        
        # 设计剪力
        V_ed = q_uls * x
        
        # 配筋率
        rho = self.calculate_reinforcement().area_provided / (1000 * self.d * 1000)
        
        # 混凝土抗剪承载力 (Eurocode 2)
        k = min(1 + math.sqrt(200 / (self.d * 1000)), 2)
        v_rd_c = max(
            0.12 * k * (100 * rho * self.concrete.fck.value) ** (1/3),
            0.035 * k ** 1.5 * math.sqrt(self.concrete.fck.value)
        )
        
        V_rd_c = v_rd_c * 1000 * self.d * 1000 / 1000  # kN/m
        
        status = "PASS" if V_rd_c > V_ed else "FAIL"
        
        return ShearCheckResult(
            design_shear_force=round(V_ed, 3),
            shear_resistance=round(V_rd_c, 3),
            shear_stress=round(v_rd_c, 3),
            status=status
        )
    
    def run_full_analysis(self) -> Dict[str, Any]:
        """
        运行完整分析
        
        Returns:
            Dict: 包含所有验算结果的字典
        """
        return {
            "基础信息": {
                "基础宽度": f"{self.B:.3f} m",
                "基础厚度": f"{self.h:.3f} m",
                "有效高度": f"{self.d:.3f} m",
                "墙宽度": f"{self.wall_w:.3f} m"
            },
            "SLS地基压力": self.calculate_bearing_pressure_sls(),
            "ULS地基压力": self.calculate_bearing_pressure_uls(),
            "横向配筋": self.calculate_reinforcement().model_dump(),
            "抗剪验算": self.check_shear().model_dump()
        }


# ============================================================================
# 工具函数
# ============================================================================

def create_pad_foundation_calculator(
    length: float,
    width: float,
    thickness: float = 300,
    column_length: float = 400,
    column_width: float = 400,
    col_pos_xdir: Optional[float] = None,
    col_pos_ydir: Optional[float] = None,
    permanent_axial: float = 0,
    imposed_axial: float = 0,
    wind_axial: float = 0,
    bearing_capacity: float = 150,
    fck: int = 25,
    fyk: int = 460,
    concrete_cover: float = 30,
    bar_diameter_x: int = 16,
    bar_diameter_y: int = 16
) -> PadFoundationCalculator:
    """
    快速创建独立基础计算器的工厂函数
    
    Args:
        length: 基础长度 (mm)
        width: 基础宽度 (mm)
        thickness: 基础厚度 (mm)
        column_length: 柱长度 (mm)
        column_width: 柱宽度 (mm)
        col_pos_xdir: 柱X方向位置 (mm)
        col_pos_ydir: 柱Y方向位置 (mm)
        permanent_axial: 永久轴向荷载 (kN)
        imposed_axial: 可变轴向荷载 (kN)
        wind_axial: 风荷载轴向分量 (kN)
        bearing_capacity: 地基承载力 (kN/m²)
        fck: 混凝土强度等级
        fyk: 钢筋强度等级
        concrete_cover: 保护层厚度 (mm)
        bar_diameter_x: X方向钢筋直径 (mm)
        bar_diameter_y: Y方向钢筋直径 (mm)
    
    Returns:
        PadFoundationCalculator: 独立基础计算器实例
    """
    geometry = FoundationGeometry(
        length=length,
        width=width,
        thickness=thickness,
        column_length=column_length,
        column_width=column_width,
        col_pos_xdir=col_pos_xdir,
        col_pos_ydir=col_pos_ydir
    )
    
    loads = FoundationLoads(
        permanent_axial=permanent_axial,
        imposed_axial=imposed_axial,
        wind_axial=wind_axial
    )
    
    soil = SoilParameters(bearing_capacity=bearing_capacity)
    
    concrete = ConcreteParameters(
        fck=ConcreteGrade(fck),
        fyk=SteelGrade(fyk),
        concrete_cover=concrete_cover,
        bar_diameter_x=BarDiameter(bar_diameter_x),
        bar_diameter_y=BarDiameter(bar_diameter_y)
    )
    
    return PadFoundationCalculator(geometry, loads, soil, concrete)


def create_strip_foundation_calculator(
    length: float,
    width: float,
    thickness: float = 300,
    wall_width: float = 300,
    wall_position: Optional[float] = None,
    permanent_axial: float = 0,
    imposed_axial: float = 0,
    wind_axial: float = 0,
    bearing_capacity: float = 150,
    fck: int = 25,
    fyk: int = 460,
    concrete_cover: float = 30,
    bar_diameter: int = 16
) -> StripFoundationCalculator:
    """
    快速创建条形基础计算器的工厂函数
    
    Args:
        length: 基础长度 (mm)
        width: 基础宽度 (mm)
        thickness: 基础厚度 (mm)
        wall_width: 墙宽度 (mm)
        wall_position: 墙位置 (mm)
        permanent_axial: 永久轴向荷载 (kN/m)
        imposed_axial: 可变轴向荷载 (kN/m)
        wind_axial: 风荷载轴向分量 (kN/m)
        bearing_capacity: 地基承载力 (kN/m²)
        fck: 混凝土强度等级
        fyk: 钢筋强度等级
        concrete_cover: 保护层厚度 (mm)
        bar_diameter: 钢筋直径 (mm)
    
    Returns:
        StripFoundationCalculator: 条形基础计算器实例
    """
    geometry = StripFoundationGeometry(
        length=length,
        width=width,
        thickness=thickness,
        wall_width=wall_width,
        wall_position=wall_position
    )
    
    loads = FoundationLoads(
        permanent_axial=permanent_axial,
        imposed_axial=imposed_axial,
        wind_axial=wind_axial
    )
    
    soil = SoilParameters(bearing_capacity=bearing_capacity)
    
    concrete = ConcreteParameters(
        fck=ConcreteGrade(fck),
        fyk=SteelGrade(fyk),
        concrete_cover=concrete_cover,
        bar_diameter_x=BarDiameter(bar_diameter),
        bar_diameter_y=BarDiameter(bar_diameter)
    )
    
    return StripFoundationCalculator(geometry, loads, soil, concrete)


# ============================================================================
# 主程序入口
# ============================================================================

if __name__ == "__main__":
    # 示例1: 独立基础计算
    print("=" * 60)
    print("示例1: 独立基础承载力计算")
    print("=" * 60)
    
    # 创建独立基础计算器
    pad_calc = create_pad_foundation_calculator(
        length=2400,           # 基础长度 2.4m
        width=2400,            # 基础宽度 2.4m
        thickness=650,         # 基础厚度 0.65m
        column_length=400,     # 柱长度 0.4m
        column_width=400,      # 柱宽度 0.4m
        permanent_axial=1000,  # 永久荷载 1000kN
        imposed_axial=500,     # 可变荷载 500kN
        wind_axial=200,        # 风荷载 200kN
        bearing_capacity=200,  # 地基承载力 200kN/m²
        fck=30,                # C30混凝土
        fyk=460,               # 460MPa钢筋
        concrete_cover=40,     # 保护层40mm
        bar_diameter_x=16,     # X向钢筋直径16mm
        bar_diameter_y=16      # Y向钢筋直径16mm
    )
    
    # 运行完整分析
    results = pad_calc.run_full_analysis()
    
    # 打印结果
    for category, data in results.items():
        print(f"\n【{category}】")
        if isinstance(data, dict):
            for key, value in data.items():
                print(f"  {key}: {value}")
        else:
            print(f"  {data}")
    
    # 示例2: 条形基础计算
    print("\n" + "=" * 60)
    print("示例2: 条形基础承载力计算")
    print("=" * 60)
    
    strip_calc = create_strip_foundation_calculator(
        length=5000,           # 基础长度 5m
        width=1200,            # 基础宽度 1.2m
        thickness=400,         # 基础厚度 0.4m
        wall_width=300,        # 墙宽 0.3m
        permanent_axial=150,   # 永久荷载 150kN/m
        imposed_axial=75,      # 可变荷载 75kN/m
        bearing_capacity=150,  # 地基承载力 150kN/m²
        fck=25,                # C25混凝土
        fyk=460,               # 460MPa钢筋
        bar_diameter=16        # 钢筋直径16mm
    )
    
    results = strip_calc.run_full_analysis()
    
    for category, data in results.items():
        print(f"\n【{category}】")
        if isinstance(data, dict):
            for key, value in data.items():
                print(f"  {key}: {value}")
        else:
            print(f"  {data}")
    
    # 示例3: 使用Pydantic模型直接创建
    print("\n" + "=" * 60)
    print("示例3: 使用Pydantic模型创建")
    print("=" * 60)
    
    geometry = FoundationGeometry(
        length=3000,
        width=2500,
        thickness=700,
        column_length=500,
        column_width=400
    )
    
    loads = FoundationLoads(
        permanent_axial=2000,
        imposed_axial=800,
        permanent_horizontal_x=100,
        permanent_moment_x=150
    )
    
    soil = SoilParameters(
        bearing_capacity=250,
        soil_type=SoilType.SAND,
        soil_depth_above=300
    )
    
    concrete = ConcreteParameters(
        fck=ConcreteGrade.C35,
        fyk=SteelGrade.S500,
        concrete_cover=50,
        bar_diameter_x=BarDiameter.D20,
        bar_diameter_y=BarDiameter.D16
    )
    
    calculator = PadFoundationCalculator(geometry, loads, soil, concrete)
    
    # 单独计算地基压力
    pressure_result = calculator.calculate_bearing_pressure_sls()
    print(f"\n地基压力验算结果:")
    print(f"  最大压力: {pressure_result.q_max} kN/m²")
    print(f"  最小压力: {pressure_result.q_min} kN/m²")
    print(f"  平均压力: {pressure_result.q_avg} kN/m²")
    print(f"  偏心距X: {pressure_result.eccentricity_x} mm")
    print(f"  偏心距Y: {pressure_result.eccentricity_y} mm")
    print(f"  状态: {pressure_result.status}")
    
    # 配筋计算
    reinf_x = calculator.calculate_reinforcement_x()
    print(f"\nX方向配筋:")
    print(f"  所需钢筋面积: {reinf_x.area_required} mm²/m")
    print(f"  提供钢筋面积: {reinf_x.area_provided} mm²/m")
    print(f"  钢筋直径: {reinf_x.bar_diameter} mm")
    print(f"  钢筋间距: {reinf_x.bar_spacing} mm")
    print(f"  状态: {reinf_x.status}")
