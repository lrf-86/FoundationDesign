import sys
sys.path.insert(0, 'FoundationDesign')

spec = {}
exec(open('FoundationDesign/bearingcapacity.py', encoding='utf-8').read(), spec)

PadFoundationParams = spec['PadFoundationParams']
StripFoundationParams = spec['StripFoundationParams']
PadFoundationBearingCapacity = spec['PadFoundationBearingCapacity']
StripFoundationBearingCapacity = spec['StripFoundationBearingCapacity']

print("Testing module syntax...")
pad_params = PadFoundationParams(
    foundation_length=2.5,
    foundation_width=2.5,
    column_length=0.5,
    column_width=0.5,
    permanent_load=1000,
    variable_load=300,
    soil_bearing_capacity=180,
    foundation_depth=1.5
)
print("PadFoundationParams OK")

pad_calc = PadFoundationBearingCapacity(pad_params)
result = pad_calc.check_bearing_capacity()
print(f"Result: avg={result.base_pressure_avg:.1f}, allowable={result.allowable_bearing:.1f}")
print(f"Satisfied: {result.is_satisfied}")
print("ALL TESTS PASSED!")
