from django.core.exceptions import ValidationError

def _digits(v:str):
    if not v or not v.isdigit():
        raise ValidationError("Разрешены только цифры.")
    return v

def validate_bik(v:str):
    v = _digits(v)
    if len(v) != 9:
        raise ValidationError("БИК должен содержать 9 цифр.")

def validate_inn(v:str):
    v = _digits(v)
    if len(v) not in (10,12):
        raise ValidationError("ИНН должен содержать 10 или 12 цифр.")
    def checksum(nums, coeffs):
        s = sum(int(a)*b for a,b in zip(nums, coeffs))
        return str((s % 11) % 10)
    if len(v)==10:
        k10 = checksum(v[:9], [2,4,10,3,5,9,4,6,8])
        if v[9] != k10: raise ValidationError("Некорректный ИНН.")
    else:
        k11 = checksum(v[:10], [7,2,4,10,3,5,9,4,6,8])
        k12 = checksum(v[:11], [3,7,2,4,10,3,5,9,4,6,8])
        if v[10]!=k11 or v[11]!=k12: raise ValidationError("Некорректный ИНН.")

def validate_rs_with_bik(rs:str, bik:str):
    rs = _digits(rs)
    if len(rs)!=20: raise ValidationError("Р/с должен содержать 20 цифр.")
    validate_bik(bik)
    control_str = (bik[-3:] + rs)
    weights = [7,3,1]*8 + [7]
    s = sum(int(d)*weights[i] for i,d in enumerate(control_str)) % 10
    if s != 0: raise ValidationError("Р/с не проходит контроль с данным БИК.")
