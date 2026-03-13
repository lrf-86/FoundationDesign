# -*- coding: utf-8 -*-
"""
建筑工程地基基础承载力计算模块
包含独立基础和条形基础的承载力计算功能
使用 Pydantic 进行数据验证
"""

import math
from typing import Optional, Tuple

from pydantic import BaseModel, Field, validator


class BaseFoundationParams(BaseModel):
    """地基基础参数基类"""
    soil_bearing_capacity: float = Field(
        150.0,
        description="地基承载力特征值 (kN/m²)",
        ge=0
    )
    foundation_depth: float = Field(
        1.5,
        description="基础埋置深度 (m)",
        gt=0
    )
    soil_unit_weight: float = Field(
        18.0,
        description="土的重度 (kN/m³)",
        gt=0
    )
    groundwater_depth: Optional[float] = Field(
        None,
        description="地下水位深度 (m)",
        ge=0
    )

    @validator('groundwater_depth')
    def check_groundwater_depth(cls, v, values):
        if v is not None and 'foundation_depth' in values:
            if v < 0:
                raise ValueError("地下水位深度不能小于0")
        return v


class PadFoundationParams(BaseFoundationParams):
    """独立基础参数模型"""
    foundation_length: float = Field(
        description="基础长度 (m)",
        gt=0
    )
    foundation_width: float = Field(
        description="基础宽度 (m)",
        gt=0
    )
    column_length: float = Field(
        description="柱截面长度 (m)",
        gt=0
    )
    column_width: float = Field(
        description="柱截面宽度 (m)",
        gt=0
    )
    permanent_load: float = Field(
        description="永久荷载标准值 (kN)",
        default=0.0
    )
    variable_load: float = Field(
        description="可变荷载标准值 (kN)",
        default=0.0
    )
    permanent_moment_x: float = Field(
        description="x方向永久弯矩 (kN·m)",
        default=0.0
    )
    variable_moment_x: float = Field(
        description="x方向可变弯矩 (kN·m)",
        default=0.0
    )
    permanent_moment_y: float = Field(
        description="y方向永久弯矩 (kN·m)",
        default=0.0
    )
    variable_moment_y: float = Field(
        description="y方向可变弯矩 (kN·m)",
        default=0.0
    )


class StripFoundationParams(BaseFoundationParams):
    """条形基础参数模型"""
    foundation_width: float = Field(
        description="基础宽度 (m)",
        gt=0
    )
    wall_thickness: float = Field(
        description="墙体厚度 (m)",
        gt=0
    )
    permanent_load_per_meter: float = Field(
        description="每延米永久荷载标准值 (kN/m)",
        default=0.0
    )
    variable_load_per_meter: float = Field(
        description="每延米可变荷载标准值 (kN/m)",
        default=0.0
    )
    permanent_moment_per_meter: float = Field(
        description="每延米永久弯矩 (kN·m/m)",
        default=0.0
    )
    variable_moment_per_meter: float = Field(
        description="每延米可变弯矩 (kN·m/m)",
        default=0.0
    )


class BearingCapacityResult(BaseModel):
    """承载力计算结果模型"""
    base_pressure_max: float = Field(description="基底最大压力 (kPa)")
    base_pressure_min: float = Field(description="基底最小压力 (kPa)")
    base_pressure_avg: float = Field(description="基底平均压力 (kPa)")
    allowable_bearing: float = Field(description="修正后的地基承载力特征值 (kPa)")
    is_satisfied: bool = Field(description="承载力是否满足要求")
    eccentricity: Optional[float] = Field(None, description="基础偏心距 (m)")


class BaseBearingCapacity:
    """地基基础承载力计算基类"""

    def __init__(self):
        pass

    def _get_effective_unit_weight(
        self,
        foundation_depth: float,
        soil_unit_weight: float,
        groundwater_depth: Optional[float]
    ) -> float:
        """
        计算有效重度
        考虑地下水位影响
        """
        if groundwater_depth is None or groundwater_depth >= foundation_depth:
            return soil_unit_weight
        elif groundwater_depth <= 0:
            return soil_unit_weight - 10
        else:
            h_submerged = foundation_depth - groundwater_depth
            h_natural = groundwater_depth
            return (h_natural * soil_unit_weight + h_submerged * (soil_unit_weight - 10)) / foundation_depth

    def bearing_capacity_correction(
        self,
        soil_bearing_capacity: float,
        foundation_depth: float,
        foundation_width: float,
        soil_unit_weight: float,
        groundwater_depth: Optional[float] = None
    ) -> float:
        """
        地基承载力修正
        根据《建筑地基基础设计规范》GB 50007
        采用简化的深度和宽度修正
        """
        gamma_m = self._get_effective_unit_weight(foundation_depth, soil_unit_weight, groundwater_depth)

        eta_d = 1.0
        eta_b = 0.3

        depth_correction = eta_d * gamma_m * (foundation_depth - 0.5)

        if foundation_width <= 3.0:
            width_correction = 0.0
        elif foundation_width >= 6.0:
            width_correction = eta_b * gamma_m * (6.0 - 3.0)
        else:
            width_correction = eta_b * gamma_m * (foundation_width - 3.0)

        corrected_bearing = soil_bearing_capacity + depth_correction + width_correction

        return max(corrected_bearing, soil_bearing_capacity * 1.1)


class PadFoundationBearingCapacity(BaseBearingCapacity):
    """独立基础承载力计算类"""

    def __init__(self, params: PadFoundationParams):
        super().__init__()
        self.params = params

    def foundation_area(self) -> float:
        """计算基础底面积 (m²)"""
        return self.params.foundation_length * self.params.foundation_width

    def total_vertical_load(self) -> float:
        """计算总竖向荷载设计值 (kN)"""
        total_load = (1.35 * self.params.permanent_load +
                      1.5 * self.params.variable_load)

        foundation_weight = (self.params.foundation_length *
                             self.params.foundation_width *
                             self.params.foundation_depth *
                             24.0)

        return total_load + foundation_weight

    def total_moment_x(self) -> float:
        """计算x方向总弯矩设计值 (kN·m)"""
        return 1.35 * self.params.permanent_moment_x + 1.5 * self.params.variable_moment_x

    def total_moment_y(self) -> float:
        """计算y方向总弯矩设计值 (kN·m)"""
        return 1.35 * self.params.permanent_moment_y + 1.5 * self.params.variable_moment_y

    def section_modulus_x(self) -> float:
        """计算x方向基础抵抗矩 (m³)"""
        return (self.params.foundation_length *
                self.params.foundation_width ** 2) / 6.0

    def section_modulus_y(self) -> float:
        """计算y方向基础抵抗矩 (m³)"""
        return (self.params.foundation_width *
                self.params.foundation_length ** 2) / 6.0

    def calculate_base_pressures(self) -> Tuple[float, float, float]:
        """
        计算基底压力
        返回: (最大压力, 最小压力, 平均压力) 单位: kPa
        """
        area = self.foundation_area()
        total_load = self.total_vertical_load()
        mx = self.total_moment_x()
        my = self.total_moment_y()

        wx = self.section_modulus_x()
        wy = self.section_modulus_y()

        p_avg = total_load / area

        if abs(mx) < 1e-10 and abs(my) < 1e-10:
            return p_avg, p_avg, p_avg

        p_x = abs(mx) / wx if wx > 0 else 0
        p_y = abs(my) / wy if wy > 0 else 0

        p_max = p_avg + p_x + p_y
        p_min = p_avg - p_x - p_y

        return p_max, p_min, p_avg

    def calculate_eccentricity(self) -> float:
        """计算基础偏心距 (m)"""
        total_load = self.total_vertical_load()

        if abs(total_load) < 1e-10:
            return 0.0

        mx = self.total_moment_x()
        my = self.total_moment_y()
        total_moment = math.sqrt(mx ** 2 + my ** 2)

        return total_moment / total_load

    def check_bearing_capacity(self) -> BearingCapacityResult:
        """
        承载力验算
        返回计算结果对象
        """
        p_max, p_min, p_avg = self.calculate_base_pressures()

        allowable = self.bearing_capacity_correction(
            self.params.soil_bearing_capacity,
            self.params.foundation_depth,
            min(self.params.foundation_length, self.params.foundation_width),
            self.params.soil_unit_weight,
            self.params.groundwater_depth
        )

        eccentricity = self.calculate_eccentricity()

        p_k_avg = ((self.params.permanent_load + self.params.variable_load) /
                   self.foundation_area() +
                   24.0 * self.params.foundation_depth)

        p_k_max = p_k_avg
        if abs(self.params.permanent_moment_x + self.params.variable_moment_x) > 1e-10:
            p_k_max += (abs(self.params.permanent_moment_x + self.params.variable_moment_x) /
                        self.section_modulus_x())
        if abs(self.params.permanent_moment_y + self.params.variable_moment_y) > 1e-10:
            p_k_max += (abs(self.params.permanent_moment_y + self.params.variable_moment_y) /
                        self.section_modulus_y())

        is_satisfied = (p_k_avg <= allowable and p_k_max <= 1.2 * allowable)

        return BearingCapacityResult(
            base_pressure_max=p_k_max,
            base_pressure_min=p_k_avg - (p_k_max - p_k_avg),
            base_pressure_avg=p_k_avg,
            allowable_bearing=allowable,
            is_satisfied=is_satisfied,
            eccentricity=eccentricity
        )


class StripFoundationBearingCapacity(BaseBearingCapacity):
    """条形基础承载力计算类"""

    def __init__(self, params: StripFoundationParams):
        super().__init__()
        self.params = params

    def total_vertical_load_per_meter(self) -> float:
        """计算每延米总竖向荷载设计值 (kN/m)"""
        total_load = (1.35 * self.params.permanent_load_per_meter +
                      1.5 * self.params.variable_load_per_meter)

        foundation_weight = self.params.foundation_width * self.params.foundation_depth * 24.0

        return total_load + foundation_weight

    def total_moment_per_meter(self) -> float:
        """计算每延米总弯矩设计值 (kN·m/m)"""
        return (1.35 * self.params.permanent_moment_per_meter +
                1.5 * self.params.variable_moment_per_meter)

    def section_modulus_per_meter(self) -> float:
        """计算每延米基础抵抗矩 (m³/m)"""
        return self.params.foundation_width ** 2 / 6.0

    def calculate_base_pressures(self) -> Tuple[float, float, float]:
        """
        计算基底压力 (每延米)
        返回: (最大压力, 最小压力, 平均压力) 单位: kPa
        """
        total_load = self.total_vertical_load_per_meter()
        total_moment = self.total_moment_per_meter()
        w = self.section_modulus_per_meter()

        p_avg = total_load / self.params.foundation_width

        if abs(total_moment) < 1e-10:
            return p_avg, p_avg, p_avg

        p_delta = abs(total_moment) / w

        p_max = p_avg + p_delta
        p_min = p_avg - p_delta

        return p_max, p_min, p_avg

    def calculate_eccentricity(self) -> float:
        """计算基础偏心距 (m)"""
        total_load = self.total_vertical_load_per_meter()

        if abs(total_load) < 1e-10:
            return 0.0

        total_moment = self.total_moment_per_meter()
        return abs(total_moment) / total_load

    def check_bearing_capacity(self) -> BearingCapacityResult:
        """
        承载力验算
        返回计算结果对象
        """
        p_max, p_min, p_avg = self.calculate_base_pressures()

        allowable = self.bearing_capacity_correction(
            self.params.soil_bearing_capacity,
            self.params.foundation_depth,
            1.0,
            self.params.soil_unit_weight,
            self.params.groundwater_depth
        )

        eccentricity = self.calculate_eccentricity()

        p_k_avg = ((self.params.permanent_load_per_meter + self.params.variable_load_per_meter) /
                   self.params.foundation_width +
                   24.0 * self.params.foundation_depth)

        moment_k = (self.params.permanent_moment_per_meter +
                    self.params.variable_moment_per_meter)

        p_k_max = p_k_avg
        if abs(moment_k) > 1e-10:
            p_k_max += abs(moment_k) / self.section_modulus_per_meter()

        is_satisfied = (p_k_avg <= allowable and p_k_max <= 1.2 * allowable)

        return BearingCapacityResult(
            base_pressure_max=p_k_max,
            base_pressure_min=p_k_avg - (p_k_max - p_k_avg),
            base_pressure_avg=p_k_avg,
            allowable_bearing=allowable,
            is_satisfied=is_satisfied,
            eccentricity=eccentricity
        )
