"""
建筑工程地基基础承载力计算模块

本模块提供独立基础和条形基础的承载力计算功能，基于中国建筑地基基础设计规范(GB 50007-2011)。
包含Pydantic数据模型用于输入验证，支持多种地基承载力计算方法。

作者：FoundationDesign Team
版本：1.0.0
"""

from typing import Optional, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field
import math


class SoilType(str, Enum):
    """土质类型枚举"""
    CLAY = "粘性土"
    SILT = "粉土"
    SAND = "砂土"
    GRAVEL = "碎石土"
    ROCK = "岩石"


class LoadType(str, Enum):
    """荷载类型枚举"""
    STANDARD = "标准值"
    DESIGN = "设计值"


class SoilParameters(BaseModel):
    """
    土体参数模型
    
    用于定义地基土的物理力学性质参数。
    
    Attributes
    ----------
    soil_type : SoilType
        土质类型
    cohesion : float
        粘聚力c (kPa)，默认0
    friction_angle : float
        内摩擦角φ (度)，范围0-45，默认0
    unit_weight : float
        土的重度γ (kN/m³)，默认18.0
    bearing_capacity_characteristic : float
        地基承载力特征值fak (kPa)，默认150.0
    deformation_modulus : Optional[float]
        变形模量E0 (MPa)，可选
    """
    
    soil_type: SoilType = Field(..., description="土质类型")
    cohesion: float = Field(default=0, ge=0, description="粘聚力c (kPa)")
    friction_angle: float = Field(default=0, ge=0, le=45, description="内摩擦角φ (度)")
    unit_weight: float = Field(default=18.0, gt=0, description="土的重度γ (kN/m³)")
    bearing_capacity_characteristic: float = Field(
        default=150.0, gt=0, description="地基承载力特征值fak (kPa)"
    )
    deformation_modulus: Optional[float] = Field(
        default=None, gt=0, description="变形模量E0 (MPa)"
    )
    
    model_config = {"use_enum_values": True}


class FoundationGeometry(BaseModel):
    """
    基础几何参数模型
    
    用于定义基础的几何尺寸参数。
    
    Attributes
    ----------
    foundation_length : float
        基础长度L (m)
    foundation_width : float
        基础宽度B (m)
    foundation_depth : float
        基础埋深d (m)，默认1.5
    foundation_thickness : float
        基础厚度h (m)，默认0.5
    """
    
    foundation_length: float = Field(..., gt=0, description="基础长度L (m)")
    foundation_width: float = Field(..., gt=0, description="基础宽度B (m)")
    foundation_depth: float = Field(default=1.5, ge=0, description="基础埋深d (m)")
    foundation_thickness: float = Field(default=0.5, gt=0, description="基础厚度h (m)")
    
    @property
    def area(self) -> float:
        """计算基础底面积 A = L × B (m²)"""
        return self.foundation_length * self.foundation_width
    
    @property
    def perimeter(self) -> float:
        """计算基础周长 (m)"""
        return 2 * (self.foundation_length + self.foundation_width)
    
    @property
    def moment_of_inertia_x(self) -> float:
        """计算绕X轴的惯性矩 Ix = L×B³/12 (m⁴)"""
        return self.foundation_length * self.foundation_width ** 3 / 12
    
    @property
    def moment_of_inertia_y(self) -> float:
        """计算绕Y轴的惯性矩 Iy = B×L³/12 (m⁴)"""
        return self.foundation_width * self.foundation_length ** 3 / 12
    
    @property
    def section_modulus_x(self) -> float:
        """计算绕X轴的截面模量 Wx = Ix/(B/2) (m³)"""
        return self.moment_of_inertia_x / (self.foundation_width / 2)
    
    @property
    def section_modulus_y(self) -> float:
        """计算绕Y轴的截面模量 Wy = Iy/(L/2) (m³)"""
        return self.moment_of_inertia_y / (self.foundation_length / 2)


class LoadParameters(BaseModel):
    """
    荷载参数模型
    
    用于定义作用在基础上的各类荷载。
    
    Attributes
    ----------
    vertical_load : float
        竖向荷载N (kN)
    moment_x : float
        绕X轴弯矩Mx (kN·m)，默认0
    moment_y : float
        绕Y轴弯矩My (kN·m)，默认0
    horizontal_load_x : float
        X方向水平荷载Hx (kN)，默认0
    horizontal_load_y : float
        Y方向水平荷载Hy (kN)，默认0
    load_type : LoadType
        荷载类型，默认标准值
    """
    
    vertical_load: float = Field(..., ge=0, description="竖向荷载N (kN)")
    moment_x: float = Field(default=0, description="绕X轴弯矩Mx (kN·m)")
    moment_y: float = Field(default=0, description="绕Y轴弯矩My (kN·m)")
    horizontal_load_x: float = Field(default=0, description="X方向水平荷载Hx (kN)")
    horizontal_load_y: float = Field(default=0, description="Y方向水平荷载Hy (kN)")
    load_type: LoadType = Field(default=LoadType.STANDARD, description="荷载类型")
    
    model_config = {"use_enum_values": True}
    
    @property
    def resultant_moment(self) -> float:
        """计算合力矩 M = √(Mx² + My²) (kN·m)"""
        return math.sqrt(self.moment_x ** 2 + self.moment_y ** 2)
    
    @property
    def resultant_horizontal_load(self) -> float:
        """计算水平合力 H = √(Hx² + Hy²) (kN)"""
        return math.sqrt(self.horizontal_load_x ** 2 + self.horizontal_load_y ** 2)


class IsolatedFoundationBearingCapacity:
    """
    独立基础承载力计算类
    
    基于GB 50007-2011《建筑地基基础设计规范》进行承载力计算，
    包括地基承载力修正、基底压力计算、偏心验算、稳定性验算等。
    
    Attributes
    ----------
    geometry : FoundationGeometry
        基础几何参数
    soil : SoilParameters
        土体参数
    loads : LoadParameters
        荷载参数
    
    Example
    -------
    >>> geometry = FoundationGeometry(foundation_length=3.0, foundation_width=3.0, foundation_depth=1.5)
    >>> soil = SoilParameters(soil_type="粘性土", bearing_capacity_characteristic=180.0)
    >>> loads = LoadParameters(vertical_load=800.0, moment_x=50.0)
    >>> foundation = IsolatedFoundationBearingCapacity(geometry, soil, loads)
    >>> result = foundation.check_bearing_capacity()
    """
    
    def __init__(
        self,
        geometry: FoundationGeometry,
        soil: SoilParameters,
        loads: LoadParameters
    ):
        """
        初始化独立基础承载力计算对象
        
        Parameters
        ----------
        geometry : FoundationGeometry
            基础几何参数模型
        soil : SoilParameters
            土体参数模型
        loads : LoadParameters
            荷载参数模型
        """
        self.geometry = geometry
        self.soil = soil
        self.loads = loads
        self._validate_inputs()
    
    def _validate_inputs(self) -> None:
        """验证输入参数的有效性"""
        if self.geometry.foundation_length < self.geometry.foundation_width:
            raise ValueError("基础长度应大于或等于基础宽度")
    
    def calculate_depth_factor(self) -> float:
        """
        计算深度修正系数ηd
        
        根据GB 50007-2011第5.2.4条确定深度修正系数。
        
        Returns
        -------
        float
            深度修正系数ηd
        """
        soil_type = self.soil.soil_type
        
        depth_factors = {
            SoilType.CLAY: 1.0,
            SoilType.SILT: 1.5,
            SoilType.SAND: 3.0,
            SoilType.GRAVEL: 4.4,
            SoilType.ROCK: 1.0
        }
        
        return depth_factors.get(SoilType(soil_type), 1.0)
    
    def calculate_width_factor(self) -> float:
        """
        计算宽度修正系数ηb
        
        根据GB 50007-2011第5.2.4条确定宽度修正系数。
        当基础宽度b≤3m时，取ηb=0。
        
        Returns
        -------
        float
            宽度修正系数ηb
        """
        soil_type = self.soil.soil_type
        width = self.geometry.foundation_width
        
        if width <= 3.0:
            return 0.0
        
        width_factors = {
            SoilType.CLAY: 0.3,
            SoilType.SILT: 0.5,
            SoilType.SAND: 2.0,
            SoilType.GRAVEL: 3.0,
            SoilType.ROCK: 0.0
        }
        
        return width_factors.get(SoilType(soil_type), 0.0)
    
    def calculate_bearing_capacity(self) -> Dict[str, float]:
        """
        计算修正后的地基承载力特征值
        
        根据GB 50007-2011公式(5.2.4)：
        fa = fak + ηb×γ×(b-3) + ηd×γm×(d-0.5)
        
        其中：
        - fak: 地基承载力特征值
        - ηb: 宽度修正系数
        - ηd: 深度修正系数
        - γ: 基础底面以下土的重度
        - γm: 基础底面以上土的加权平均重度
        - b: 基础宽度，大于6m按6m取值
        - d: 基础埋深
        
        Returns
        -------
        Dict[str, float]
            包含修正后承载力特征值及各修正项的字典
        """
        fak = self.soil.bearing_capacity_characteristic
        gamma = self.soil.unit_weight
        b = min(self.geometry.foundation_width, 6.0)
        d = self.geometry.foundation_depth
        
        eta_b = self.calculate_width_factor()
        eta_d = self.calculate_depth_factor()
        
        gamma_m = gamma
        
        width_correction = eta_b * gamma * (b - 3.0) if b > 3.0 else 0.0
        depth_correction = eta_d * gamma_m * (d - 0.5) if d > 0.5 else 0.0
        
        fa = fak + width_correction + depth_correction
        
        return {
            "特征值fak_kPa": round(fak, 2),
            "宽度修正系数ηb": round(eta_b, 2),
            "深度修正系数ηd": round(eta_d, 2),
            "宽度修正项_kPa": round(width_correction, 2),
            "深度修正项_kPa": round(depth_correction, 2),
            "修正后承载力特征值fa_kPa": round(fa, 2)
        }
    
    def calculate_eccentricity(self) -> Dict[str, float]:
        """
        计算偏心距
        
        偏心距计算公式：
        ex = My / N
        ey = Mx / N
        
        Returns
        -------
        Dict[str, float]
            包含各方向偏心距的字典
        """
        N = self.loads.vertical_load
        
        if N == 0:
            return {
                "X方向偏心距ex_m": 0.0,
                "Y方向偏心距ey_m": 0.0,
                "相对偏心距ex_L": 0.0,
                "相对偏心距ey_B": 0.0
            }
        
        ex = abs(self.loads.moment_y) / N
        ey = abs(self.loads.moment_x) / N
        
        L = self.geometry.foundation_length
        B = self.geometry.foundation_width
        
        return {
            "X方向偏心距ex_m": round(ex, 4),
            "Y方向偏心距ey_m": round(ey, 4),
            "相对偏心距ex_L": round(ex / L, 4),
            "相对偏心距ey_B": round(ey / B, 4)
        }
    
    def calculate_base_pressure(self) -> Dict[str, float]:
        """
        计算基底压力
        
        当偏心距较小时(e ≤ b/6)：
        pmax = N/A + M/W
        pmin = N/A - M/W
        
        当偏心距较大时(e > b/6)，基底出现零应力区：
        pmax = 2N / (3a×l)
        
        Returns
        -------
        Dict[str, float]
            包含基底压力的字典
        """
        N = self.loads.vertical_load
        A = self.geometry.area
        Mx = self.loads.moment_x
        My = self.loads.moment_y
        
        eccentricity = self.calculate_eccentricity()
        ex = eccentricity["X方向偏心距ex_m"]
        ey = eccentricity["Y方向偏心距ey_m"]
        
        L = self.geometry.foundation_length
        B = self.geometry.foundation_width
        
        p_avg = N / A
        
        if ex <= L / 6 and ey <= B / 6:
            Wx = self.geometry.section_modulus_x
            Wy = self.geometry.section_modulus_y
            
            p_max = p_avg + abs(My) / Wy + abs(Mx) / Wx
            p_min = p_avg - abs(My) / Wy - abs(Mx) / Wx
            p_min = max(p_min, 0)
            
            zero_stress_ratio = 0.0
        else:
            a_x = L / 2 - ex
            a_y = B / 2 - ey
            
            if a_x > 0 and a_y > 0:
                if ex > L / 6:
                    p_max = 2 * N / (3 * a_x * B)
                elif ey > B / 6:
                    p_max = 2 * N / (3 * a_y * L)
                else:
                    p_max = N / A
            else:
                p_max = N / A
            
            p_min = 0.0
            zero_stress_ratio = max(0, (ex - L / 6) / L + (ey - B / 6) / B)
        
        return {
            "平均基底压力p_kPa": round(p_avg, 2),
            "最大基底压力pmax_kPa": round(p_max, 2),
            "最小基底压力pmin_kPa": round(p_min, 2),
            "零应力区比例": round(zero_stress_ratio, 4)
        }
    
    def check_bearing_capacity(self) -> Dict[str, Any]:
        """
        承载力验算
        
        验算条件：
        1. pk ≤ fa (平均压力验算)
        2. pmax ≤ 1.2fa (最大压力验算)
        
        Returns
        -------
        Dict[str, Any]
            包含验算结果的字典
        """
        bearing_capacity = self.calculate_bearing_capacity()
        base_pressure = self.calculate_base_pressure()
        
        fa = bearing_capacity["修正后承载力特征值fa_kPa"]
        p_avg = base_pressure["平均基底压力p_kPa"]
        p_max = base_pressure["最大基底压力pmax_kPa"]
        
        check_avg = p_avg <= fa
        check_max = p_max <= 1.2 * fa
        
        ratio_avg = round(p_avg / fa, 3) if fa > 0 else 0
        ratio_max = round(p_max / (1.2 * fa), 3) if fa > 0 else 0
        
        return {
            "平均压力验算": {
                "计算值_kPa": p_avg,
                "限值_kPa": fa,
                "利用率": ratio_avg,
                "是否满足": check_avg
            },
            "最大压力验算": {
                "计算值_kPa": p_max,
                "限值_kPa": round(1.2 * fa, 2),
                "利用率": ratio_max,
                "是否满足": check_max
            },
            "综合验算结果": check_avg and check_max
        }
    
    def check_eccentricity(self) -> Dict[str, Any]:
        """
        偏心验算
        
        根据GB 50007-2011第5.2.2条：
        - 对于无吊车厂房：e ≤ b/6
        - 对于有吊车厂房：e ≤ b/4
        
        Returns
        -------
        Dict[str, Any]
            包含偏心验算结果的字典
        """
        eccentricity = self.calculate_eccentricity()
        
        L = self.geometry.foundation_length
        B = self.geometry.foundation_width
        
        ex = eccentricity["X方向偏心距ex_m"]
        ey = eccentricity["Y方向偏心距ey_m"]
        
        return {
            "X方向偏心验算_无吊车": {
                "计算值_m": ex,
                "限值_m": round(L / 6, 4),
                "是否满足": ex <= L / 6
            },
            "Y方向偏心验算_无吊车": {
                "计算值_m": ey,
                "限值_m": round(B / 6, 4),
                "是否满足": ey <= B / 6
            },
            "X方向偏心验算_有吊车": {
                "计算值_m": ex,
                "限值_m": round(L / 4, 4),
                "是否满足": ex <= L / 4
            },
            "Y方向偏心验算_有吊车": {
                "计算值_m": ey,
                "限值_m": round(B / 4, 4),
                "是否满足": ey <= B / 4
            }
        }
    
    def calculate_overturning_stability(self) -> Dict[str, Any]:
        """
        计算抗倾覆稳定性
        
        抗倾覆稳定系数 = 抗倾覆力矩 / 倾覆力矩
        要求抗倾覆稳定系数 ≥ 1.6
        
        Returns
        -------
        Dict[str, Any]
            包含抗倾覆稳定性计算结果的字典
        """
        N = self.loads.vertical_load
        H = self.loads.resultant_horizontal_load
        d = self.geometry.foundation_depth
        
        L = self.geometry.foundation_length
        B = self.geometry.foundation_width
        
        M_resist = N * min(L, B) / 2
        M_overturn = H * d + self.loads.resultant_moment
        
        if M_overturn == 0:
            stability_factor = float('inf')
        else:
            stability_factor = M_resist / M_overturn
        
        return {
            "抗倾覆力矩_kNm": round(M_resist, 2),
            "倾覆力矩_kNm": round(M_overturn, 2),
            "抗倾覆稳定系数": round(stability_factor, 3) if stability_factor != float('inf') else "无穷大",
            "是否满足要求": stability_factor >= 1.6
        }
    
    def calculate_sliding_stability(self, friction_coefficient: float = 0.3) -> Dict[str, Any]:
        """
        计算抗滑移稳定性
        
        抗滑移稳定系数 = 抗滑力 / 滑移力
        要求抗滑移稳定系数 ≥ 1.3
        
        Parameters
        ----------
        friction_coefficient : float
            基底与土之间的摩擦系数，默认0.3
        
        Returns
        -------
        Dict[str, Any]
            包含抗滑移稳定性计算结果的字典
        """
        N = self.loads.vertical_load
        H = self.loads.resultant_horizontal_load
        
        R_sliding = N * friction_coefficient
        
        if H == 0:
            stability_factor = float('inf')
        else:
            stability_factor = R_sliding / H
        
        return {
            "抗滑力_kN": round(R_sliding, 2),
            "滑移力_kN": round(H, 2),
            "抗滑移稳定系数": round(stability_factor, 3) if stability_factor != float('inf') else "无穷大",
            "是否满足要求": stability_factor >= 1.3
        }
    
    def get_full_report(self) -> Dict[str, Any]:
        """
        获取完整的计算报告
        
        Returns
        -------
        Dict[str, Any]
            包含所有计算结果的完整报告
        """
        return {
            "基础几何参数": self.geometry.model_dump(),
            "土体参数": self.soil.model_dump(),
            "荷载参数": self.loads.model_dump(),
            "承载力计算": self.calculate_bearing_capacity(),
            "偏心距计算": self.calculate_eccentricity(),
            "基底压力计算": self.calculate_base_pressure(),
            "承载力验算": self.check_bearing_capacity(),
            "偏心验算": self.check_eccentricity(),
            "抗倾覆稳定性": self.calculate_overturning_stability(),
            "抗滑移稳定性": self.calculate_sliding_stability()
        }


class StripFoundationBearingCapacity:
    """
    条形基础承载力计算类
    
    基于GB 50007-2011《建筑地基基础设计规范》进行条形基础承载力计算。
    条形基础通常用于墙下基础，沿一个方向延伸较长。
    
    Attributes
    ----------
    geometry : FoundationGeometry
        基础几何参数
    soil : SoilParameters
        土体参数
    loads : LoadParameters
        荷载参数（单位长度荷载）
    
    Example
    -------
    >>> geometry = FoundationGeometry(foundation_length=10.0, foundation_width=2.0, foundation_depth=1.2)
    >>> soil = SoilParameters(soil_type="砂土", bearing_capacity_characteristic=200.0)
    >>> loads = LoadParameters(vertical_load=150.0, moment_x=20.0)
    >>> foundation = StripFoundationBearingCapacity(geometry, soil, loads)
    >>> result = foundation.check_bearing_capacity()
    """
    
    def __init__(
        self,
        geometry: FoundationGeometry,
        soil: SoilParameters,
        loads: LoadParameters
    ):
        """
        初始化条形基础承载力计算对象
        
        Parameters
        ----------
        geometry : FoundationGeometry
            基础几何参数模型
        soil : SoilParameters
            土体参数模型
        loads : LoadParameters
            荷载参数模型（单位长度荷载，kN/m）
        """
        self.geometry = geometry
        self.soil = soil
        self.loads = loads
        self._validate_inputs()
    
    def _validate_inputs(self) -> None:
        """验证输入参数的有效性"""
        if self.geometry.foundation_length <= self.geometry.foundation_width:
            raise ValueError("条形基础长度应大于宽度")
    
    def calculate_depth_factor(self) -> float:
        """
        计算深度修正系数ηd
        
        Returns
        -------
        float
            深度修正系数ηd
        """
        soil_type = self.soil.soil_type
        
        depth_factors = {
            SoilType.CLAY: 1.0,
            SoilType.SILT: 1.5,
            SoilType.SAND: 3.0,
            SoilType.GRAVEL: 4.4,
            SoilType.ROCK: 1.0
        }
        
        return depth_factors.get(SoilType(soil_type), 1.0)
    
    def calculate_width_factor(self) -> float:
        """
        计算宽度修正系数ηb
        
        Returns
        -------
        float
            宽度修正系数ηb
        """
        soil_type = self.soil.soil_type
        width = self.geometry.foundation_width
        
        if width <= 3.0:
            return 0.0
        
        width_factors = {
            SoilType.CLAY: 0.3,
            SoilType.SILT: 0.5,
            SoilType.SAND: 2.0,
            SoilType.GRAVEL: 3.0,
            SoilType.ROCK: 0.0
        }
        
        return width_factors.get(SoilType(soil_type), 0.0)
    
    def calculate_bearing_capacity(self) -> Dict[str, float]:
        """
        计算修正后的地基承载力特征值
        
        条形基础按单位长度计算，承载力修正公式同独立基础。
        
        Returns
        -------
        Dict[str, float]
            包含修正后承载力特征值及各修正项的字典
        """
        fak = self.soil.bearing_capacity_characteristic
        gamma = self.soil.unit_weight
        b = min(self.geometry.foundation_width, 6.0)
        d = self.geometry.foundation_depth
        
        eta_b = self.calculate_width_factor()
        eta_d = self.calculate_depth_factor()
        
        gamma_m = gamma
        
        width_correction = eta_b * gamma * (b - 3.0) if b > 3.0 else 0.0
        depth_correction = eta_d * gamma_m * (d - 0.5) if d > 0.5 else 0.0
        
        fa = fak + width_correction + depth_correction
        
        return {
            "特征值fak_kPa": round(fak, 2),
            "宽度修正系数ηb": round(eta_b, 2),
            "深度修正系数ηd": round(eta_d, 2),
            "宽度修正项_kPa": round(width_correction, 2),
            "深度修正项_kPa": round(depth_correction, 2),
            "修正后承载力特征值fa_kPa": round(fa, 2)
        }
    
    def calculate_eccentricity(self) -> Dict[str, float]:
        """
        计算偏心距
        
        对于条形基础，主要考虑垂直于基础长度方向的偏心。
        
        Returns
        -------
        Dict[str, float]
            包含偏心距的字典
        """
        N = self.loads.vertical_load
        
        if N == 0:
            return {
                "偏心距e_m": 0.0,
                "相对偏心距e_B": 0.0
            }
        
        e = abs(self.loads.moment_x) / N
        
        B = self.geometry.foundation_width
        
        return {
            "偏心距e_m": round(e, 4),
            "相对偏心距e_B": round(e / B, 4)
        }
    
    def calculate_base_pressure(self) -> Dict[str, float]:
        """
        计算基底压力
        
        条形基础按单位长度计算基底压力。
        
        Returns
        -------
        Dict[str, float]
            包含基底压力的字典
        """
        N = self.loads.vertical_load
        B = self.geometry.foundation_width
        M = self.loads.moment_x
        
        eccentricity = self.calculate_eccentricity()
        e = eccentricity["偏心距e_m"]
        
        p_avg = N / B
        
        if e <= B / 6:
            W = B ** 2 / 6
            p_max = p_avg + abs(M) / W
            p_min = p_avg - abs(M) / W
            p_min = max(p_min, 0)
            zero_stress_ratio = 0.0
        else:
            a = B / 2 - e
            if a > 0:
                p_max = 2 * N / (3 * a)
            else:
                p_max = N / B
            p_min = 0.0
            zero_stress_ratio = max(0, (e - B / 6) / B)
        
        return {
            "平均基底压力p_kPa": round(p_avg, 2),
            "最大基底压力pmax_kPa": round(p_max, 2),
            "最小基底压力pmin_kPa": round(p_min, 2),
            "零应力区比例": round(zero_stress_ratio, 4)
        }
    
    def check_bearing_capacity(self) -> Dict[str, Any]:
        """
        承载力验算
        
        Returns
        -------
        Dict[str, Any]
            包含验算结果的字典
        """
        bearing_capacity = self.calculate_bearing_capacity()
        base_pressure = self.calculate_base_pressure()
        
        fa = bearing_capacity["修正后承载力特征值fa_kPa"]
        p_avg = base_pressure["平均基底压力p_kPa"]
        p_max = base_pressure["最大基底压力pmax_kPa"]
        
        check_avg = p_avg <= fa
        check_max = p_max <= 1.2 * fa
        
        ratio_avg = round(p_avg / fa, 3) if fa > 0 else 0
        ratio_max = round(p_max / (1.2 * fa), 3) if fa > 0 else 0
        
        return {
            "平均压力验算": {
                "计算值_kPa": p_avg,
                "限值_kPa": fa,
                "利用率": ratio_avg,
                "是否满足": check_avg
            },
            "最大压力验算": {
                "计算值_kPa": p_max,
                "限值_kPa": round(1.2 * fa, 2),
                "利用率": ratio_max,
                "是否满足": check_max
            },
            "综合验算结果": check_avg and check_max
        }
    
    def check_eccentricity(self) -> Dict[str, Any]:
        """
        偏心验算
        
        Returns
        -------
        Dict[str, Any]
            包含偏心验算结果的字典
        """
        eccentricity = self.calculate_eccentricity()
        
        B = self.geometry.foundation_width
        e = eccentricity["偏心距e_m"]
        
        return {
            "偏心验算_无吊车": {
                "计算值_m": e,
                "限值_m": round(B / 6, 4),
                "是否满足": e <= B / 6
            },
            "偏心验算_有吊车": {
                "计算值_m": e,
                "限值_m": round(B / 4, 4),
                "是否满足": e <= B / 4
            }
        }
    
    def calculate_overturning_stability(self) -> Dict[str, Any]:
        """
        计算抗倾覆稳定性
        
        Returns
        -------
        Dict[str, Any]
            包含抗倾覆稳定性计算结果的字典
        """
        N = self.loads.vertical_load
        H = abs(self.loads.horizontal_load_x)
        d = self.geometry.foundation_depth
        B = self.geometry.foundation_width
        
        M_resist = N * B / 2
        M_overturn = H * d + abs(self.loads.moment_x)
        
        if M_overturn == 0:
            stability_factor = float('inf')
        else:
            stability_factor = M_resist / M_overturn
        
        return {
            "抗倾覆力矩_kNm": round(M_resist, 2),
            "倾覆力矩_kNm": round(M_overturn, 2),
            "抗倾覆稳定系数": round(stability_factor, 3) if stability_factor != float('inf') else "无穷大",
            "是否满足要求": stability_factor >= 1.6
        }
    
    def calculate_sliding_stability(self, friction_coefficient: float = 0.3) -> Dict[str, Any]:
        """
        计算抗滑移稳定性
        
        Parameters
        ----------
        friction_coefficient : float
            基底与土之间的摩擦系数，默认0.3
        
        Returns
        -------
        Dict[str, Any]
            包含抗滑移稳定性计算结果的字典
        """
        N = self.loads.vertical_load
        H = abs(self.loads.horizontal_load_x)
        
        R_sliding = N * friction_coefficient
        
        if H == 0:
            stability_factor = float('inf')
        else:
            stability_factor = R_sliding / H
        
        return {
            "抗滑力_kN": round(R_sliding, 2),
            "滑移力_kN": round(H, 2),
            "抗滑移稳定系数": round(stability_factor, 3) if stability_factor != float('inf') else "无穷大",
            "是否满足要求": stability_factor >= 1.3
        }
    
    def get_full_report(self) -> Dict[str, Any]:
        """
        获取完整的计算报告
        
        Returns
        -------
        Dict[str, Any]
            包含所有计算结果的完整报告
        """
        return {
            "基础几何参数": self.geometry.model_dump(),
            "土体参数": self.soil.model_dump(),
            "荷载参数": self.loads.model_dump(),
            "承载力计算": self.calculate_bearing_capacity(),
            "偏心距计算": self.calculate_eccentricity(),
            "基底压力计算": self.calculate_base_pressure(),
            "承载力验算": self.check_bearing_capacity(),
            "偏心验算": self.check_eccentricity(),
            "抗倾覆稳定性": self.calculate_overturning_stability(),
            "抗滑移稳定性": self.calculate_sliding_stability()
        }


class FoundationCalculator:
    """
    地基基础计算统一接口类
    
    提供统一的工厂方法用于创建不同类型的基础计算对象。
    
    Example
    -------
    >>> foundation = FoundationCalculator.create_isolated_foundation(
    ...     foundation_length=3.0,
    ...     foundation_width=3.0,
    ...     foundation_depth=1.5,
    ...     soil_type="粘性土",
    ...     bearing_capacity_characteristic=180.0,
    ...     vertical_load=800.0
    ... )
    >>> result = foundation.check_bearing_capacity()
    """
    
    @staticmethod
    def create_isolated_foundation(
        foundation_length: float,
        foundation_width: float,
        foundation_depth: float,
        soil_type: str,
        bearing_capacity_characteristic: float,
        vertical_load: float,
        moment_x: float = 0,
        moment_y: float = 0,
        horizontal_load_x: float = 0,
        horizontal_load_y: float = 0,
        cohesion: float = 0,
        friction_angle: float = 0,
        unit_weight: float = 18.0,
        foundation_thickness: float = 0.5
    ) -> IsolatedFoundationBearingCapacity:
        """
        创建独立基础计算对象的便捷方法
        
        Parameters
        ----------
        foundation_length : float
            基础长度
        foundation_width : float
            基础宽度
        foundation_depth : float
            基础埋深
        soil_type : str
            土质类型（粘性土/粉土/砂土/碎石土/岩石）
        bearing_capacity_characteristic : float
            地基承载力特征值
        vertical_load : float
            竖向荷载
        moment_x : float, optional
            绕X轴弯矩，默认0
        moment_y : float, optional
            绕Y轴弯矩，默认0
        horizontal_load_x : float, optional
            X方向水平荷载，默认0
        horizontal_load_y : float, optional
            Y方向水平荷载，默认0
        cohesion : float, optional
            粘聚力，默认0
        friction_angle : float, optional
            内摩擦角，默认0
        unit_weight : float, optional
            土的重度，默认18.0
        foundation_thickness : float, optional
            基础厚度，默认0.5
        
        Returns
        -------
        IsolatedFoundationBearingCapacity
            独立基础承载力计算对象
        """
        geometry = FoundationGeometry(
            foundation_length=foundation_length,
            foundation_width=foundation_width,
            foundation_depth=foundation_depth,
            foundation_thickness=foundation_thickness
        )
        
        soil = SoilParameters(
            soil_type=soil_type,
            cohesion=cohesion,
            friction_angle=friction_angle,
            unit_weight=unit_weight,
            bearing_capacity_characteristic=bearing_capacity_characteristic
        )
        
        loads = LoadParameters(
            vertical_load=vertical_load,
            moment_x=moment_x,
            moment_y=moment_y,
            horizontal_load_x=horizontal_load_x,
            horizontal_load_y=horizontal_load_y
        )
        
        return IsolatedFoundationBearingCapacity(geometry, soil, loads)
    
    @staticmethod
    def create_strip_foundation(
        foundation_length: float,
        foundation_width: float,
        foundation_depth: float,
        soil_type: str,
        bearing_capacity_characteristic: float,
        vertical_load: float,
        moment_x: float = 0,
        horizontal_load_x: float = 0,
        cohesion: float = 0,
        friction_angle: float = 0,
        unit_weight: float = 18.0,
        foundation_thickness: float = 0.5
    ) -> StripFoundationBearingCapacity:
        """
        创建条形基础计算对象的便捷方法
        
        Parameters
        ----------
        foundation_length : float
            基础长度
        foundation_width : float
            基础宽度
        foundation_depth : float
            基础埋深
        soil_type : str
            土质类型（粘性土/粉土/砂土/碎石土/岩石）
        bearing_capacity_characteristic : float
            地基承载力特征值
        vertical_load : float
            竖向荷载（单位长度，kN/m）
        moment_x : float, optional
            弯矩（单位长度），默认0
        horizontal_load_x : float, optional
            水平荷载（单位长度），默认0
        cohesion : float, optional
            粘聚力，默认0
        friction_angle : float, optional
            内摩擦角，默认0
        unit_weight : float, optional
            土的重度，默认18.0
        foundation_thickness : float, optional
            基础厚度，默认0.5
        
        Returns
        -------
        StripFoundationBearingCapacity
            条形基础承载力计算对象
        """
        geometry = FoundationGeometry(
            foundation_length=foundation_length,
            foundation_width=foundation_width,
            foundation_depth=foundation_depth,
            foundation_thickness=foundation_thickness
        )
        
        soil = SoilParameters(
            soil_type=soil_type,
            cohesion=cohesion,
            friction_angle=friction_angle,
            unit_weight=unit_weight,
            bearing_capacity_characteristic=bearing_capacity_characteristic
        )
        
        loads = LoadParameters(
            vertical_load=vertical_load,
            moment_x=moment_x,
            horizontal_load_x=horizontal_load_x
        )
        
        return StripFoundationBearingCapacity(geometry, soil, loads)


if __name__ == "__main__":
    print("=" * 70)
    print("              建筑工程地基基础承载力计算模块")
    print("          基于 GB 50007-2011《建筑地基基础设计规范》")
    print("=" * 70)
    
    print("\n" + "─" * 70)
    print("【示例1】独立基础承载力计算")
    print("─" * 70)
    
    isolated = FoundationCalculator.create_isolated_foundation(
        foundation_length=3.0,
        foundation_width=3.0,
        foundation_depth=1.5,
        soil_type="粘性土",
        bearing_capacity_characteristic=180.0,
        vertical_load=800.0,
        moment_x=50.0,
        moment_y=30.0,
        horizontal_load_x=20.0,
        horizontal_load_y=10.0,
        cohesion=25.0,
        friction_angle=20.0,
        unit_weight=19.0
    )
    
    report = isolated.get_full_report()
    
    print("\n▶ 承载力计算结果：")
    for key, value in report["承载力计算"].items():
        print(f"    {key}: {value}")
    
    print("\n▶ 基底压力计算结果：")
    for key, value in report["基底压力计算"].items():
        print(f"    {key}: {value}")
    
    print("\n▶ 承载力验算结果：")
    for check_name, check_result in report["承载力验算"].items():
        if isinstance(check_result, dict) and "是否满足" in check_result:
            print(f"    {check_name}: {'✓ 满足' if check_result['是否满足'] else '✗ 不满足'}")
    
    print("\n▶ 稳定性验算结果：")
    print(f"    抗倾覆稳定性: {'✓ 满足' if report['抗倾覆稳定性']['是否满足要求'] else '✗ 不满足'}")
    print(f"    抗滑移稳定性: {'✓ 满足' if report['抗滑移稳定性']['是否满足要求'] else '✗ 不满足'}")
    
    print("\n" + "─" * 70)
    print("【示例2】条形基础承载力计算")
    print("─" * 70)
    
    strip = FoundationCalculator.create_strip_foundation(
        foundation_length=10.0,
        foundation_width=2.0,
        foundation_depth=1.2,
        soil_type="砂土",
        bearing_capacity_characteristic=200.0,
        vertical_load=150.0,
        moment_x=20.0,
        horizontal_load_x=15.0,
        friction_angle=30.0,
        unit_weight=18.5
    )
    
    strip_report = strip.get_full_report()
    
    print("\n▶ 承载力计算结果：")
    for key, value in strip_report["承载力计算"].items():
        print(f"    {key}: {value}")
    
    print("\n▶ 基底压力计算结果：")
    for key, value in strip_report["基底压力计算"].items():
        print(f"    {key}: {value}")
    
    print("\n▶ 承载力验算结果：")
    for check_name, check_result in strip_report["承载力验算"].items():
        if isinstance(check_result, dict) and "是否满足" in check_result:
            print(f"    {check_name}: {'✓ 满足' if check_result['是否满足'] else '✗ 不满足'}")
    
    print("\n" + "=" * 70)
    print("                          计算完成")
    print("=" * 70)
