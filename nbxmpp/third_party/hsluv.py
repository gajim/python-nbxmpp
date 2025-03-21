# This file was taken from https://github.com/hsluv/hsluv-python
#
# Copyright (c) 2015 Alexei Boronine
#
# SPDX-License-Identifier: MIT

import math

m = [
    [3.240969941904521, -1.537383177570093, -0.498610760293],
    [-0.96924363628087, 1.87596750150772, 0.041555057407175],
    [0.055630079696993, -0.20397695888897, 1.056971514242878],
]
minv = [
    [0.41239079926595, 0.35758433938387, 0.18048078840183],
    [0.21263900587151, 0.71516867876775, 0.072192315360733],
    [0.019330818715591, 0.11919477979462, 0.95053215224966],
]
REF_Y = 1.0
REF_U = 0.19783000664283
REF_V = 0.46831999493879
KAPPA = 903.2962962
EPSILON = 0.0088564516
HEX_CHARS = "0123456789abcdef"


def _distance_line_from_origin(line):
    v = math.pow(line["slope"], 2) + 1
    return math.fabs(line["intercept"]) / math.sqrt(v)


def _length_of_ray_until_intersect(theta, line):
    return line["intercept"] / (math.sin(theta) - line["slope"] * math.cos(theta))


def _get_bounds(l):
    result = []
    sub1 = math.pow(l + 16, 3) / 1560896
    if sub1 > EPSILON:
        sub2 = sub1
    else:
        sub2 = l / KAPPA
    _g = 0
    while _g < 3:
        c = _g
        _g = _g + 1
        m1 = m[c][0]
        m2 = m[c][1]
        m3 = m[c][2]
        _g1 = 0
        while _g1 < 2:
            t = _g1
            _g1 = _g1 + 1
            top1 = (284517 * m1 - 94839 * m3) * sub2
            top2 = (838422 * m3 + 769860 * m2 + 731718 * m1) * l * sub2 - (
                769860 * t
            ) * l
            bottom = (632260 * m3 - 126452 * m2) * sub2 + 126452 * t
            result.append({"slope": top1 / bottom, "intercept": top2 / bottom})
    return result


def _max_safe_chroma_for_l(l):
    bounds = _get_bounds(l)
    _hx_min = 1.7976931348623157e308
    _g = 0
    while _g < 2:
        i = _g
        _g = _g + 1
        length = _distance_line_from_origin(bounds[i])
        if math.isnan(_hx_min):
            pass
        elif math.isnan(length):
            _hx_min = length
        else:
            _hx_min = min(_hx_min, length)
    return _hx_min


def _max_chroma_for_lh(l, h):
    hrad = h / 360 * math.pi * 2
    bounds = _get_bounds(l)
    _hx_min = 1.7976931348623157e308
    _g = 0
    while _g < len(bounds):
        bound = bounds[_g]
        _g = _g + 1
        length = _length_of_ray_until_intersect(hrad, bound)
        if length >= 0:
            if math.isnan(_hx_min):
                pass
            elif math.isnan(length):
                _hx_min = length
            else:
                _hx_min = min(_hx_min, length)
    return _hx_min


def _dot_product(a, b):
    sum_ = 0
    _g1 = 0
    _g = len(a)
    while _g1 < _g:
        i = _g1
        _g1 = _g1 + 1
        sum_ += a[i] * b[i]
    return sum_


def _from_linear(c):
    if c <= 0.0031308:
        return 12.92 * c
    return 1.055 * math.pow(c, 0.416666666666666685) - 0.055


def _to_linear(c):
    if c > 0.04045:
        return math.pow((c + 0.055) / 1.055, 2.4)
    return c / 12.92


def xyz_to_rgb(_hx_tuple):
    return [
        _from_linear(_dot_product(m[0], _hx_tuple)),
        _from_linear(_dot_product(m[1], _hx_tuple)),
        _from_linear(_dot_product(m[2], _hx_tuple)),
    ]


def rgb_to_xyz(_hx_tuple):
    rgbl = [
        _to_linear(_hx_tuple[0]),
        _to_linear(_hx_tuple[1]),
        _to_linear(_hx_tuple[2]),
    ]
    return [
        _dot_product(minv[0], rgbl),
        _dot_product(minv[1], rgbl),
        _dot_product(minv[2], rgbl),
    ]


def _y_to_l(y):
    if y <= EPSILON:
        return y / REF_Y * KAPPA
    return 116 * math.pow(y / REF_Y, 0.333333333333333315) - 16


def _l_to_y(l):
    if l <= 8:
        return REF_Y * l / KAPPA
    return REF_Y * math.pow((l + 16) / 116, 3)


def xyz_to_luv(_hx_tuple):
    x = float(_hx_tuple[0])
    y = float(_hx_tuple[1])
    z = float(_hx_tuple[2])
    divider = x + 15 * y + 3 * z
    var_u = 4 * x
    var_v = 9 * y
    if divider != 0:
        var_u = var_u / divider
        var_v = var_v / divider
    else:
        var_u = float("nan")
        var_v = float("nan")
    l = _y_to_l(y)
    if l == 0:
        return [0, 0, 0]
    u = 13 * l * (var_u - REF_U)
    v = 13 * l * (var_v - REF_V)
    return [l, u, v]


def luv_to_xyz(_hx_tuple):
    l = float(_hx_tuple[0])
    u = float(_hx_tuple[1])
    v = float(_hx_tuple[2])
    if l == 0:
        return [0, 0, 0]
    var_u = u / (13 * l) + REF_U
    var_v = v / (13 * l) + REF_V
    y = _l_to_y(l)
    x = 0 - ((9 * y * var_u) / (((var_u - 4) * var_v) - var_u * var_v))
    z = (((9 * y) - (15 * var_v * y)) - (var_v * x)) / (3 * var_v)
    return [x, y, z]


def luv_to_lch(_hx_tuple):
    l = float(_hx_tuple[0])
    u = float(_hx_tuple[1])
    v = float(_hx_tuple[2])
    _v = (u * u) + (v * v)
    if _v < 0:
        c = float("nan")
    else:
        c = math.sqrt(_v)
    if c < 0.00000001:
        h = 0
    else:
        hrad = math.atan2(v, u)
        h = hrad * 180.0 / 3.1415926535897932
        if h < 0:
            h = 360 + h
    return [l, c, h]


def lch_to_luv(_hx_tuple):
    l = float(_hx_tuple[0])
    c = float(_hx_tuple[1])
    h = float(_hx_tuple[2])
    hrad = h / 360.0 * 2 * math.pi
    u = math.cos(hrad) * c
    v = math.sin(hrad) * c
    return [l, u, v]


def hsluv_to_lch(_hx_tuple):
    h = float(_hx_tuple[0])
    s = float(_hx_tuple[1])
    l = float(_hx_tuple[2])
    if l > 99.9999999:
        return [100, 0, h]
    if l < 0.00000001:
        return [0, 0, h]
    _hx_max = _max_chroma_for_lh(l, h)
    c = _hx_max / 100 * s
    return [l, c, h]


def lch_to_hsluv(_hx_tuple):
    l = float(_hx_tuple[0])
    c = float(_hx_tuple[1])
    h = float(_hx_tuple[2])
    if l > 99.9999999:
        return [h, 0, 100]
    if l < 0.00000001:
        return [h, 0, 0]
    _hx_max = _max_chroma_for_lh(l, h)
    s = c / _hx_max * 100
    return [h, s, l]


def hpluv_to_lch(_hx_tuple):
    h = float(_hx_tuple[0])
    s = float(_hx_tuple[1])
    l = float(_hx_tuple[2])
    if l > 99.9999999:
        return [100, 0, h]
    if l < 0.00000001:
        return [0, 0, h]
    _hx_max = _max_safe_chroma_for_l(l)
    c = _hx_max / 100 * s
    return [l, c, h]


def lch_to_hpluv(_hx_tuple):
    l = float(_hx_tuple[0])
    c = float(_hx_tuple[1])
    h = float(_hx_tuple[2])
    if l > 99.9999999:
        return [h, 0, 100]
    if l < 0.00000001:
        return [h, 0, 0]
    _hx_max = _max_safe_chroma_for_l(l)
    s = c / _hx_max * 100
    return [h, s, l]


def rgb_to_hex(_hx_tuple):
    h = "#"
    _g = 0
    while _g < 3:
        i = _g
        _g = _g + 1
        chan = float(_hx_tuple[i])
        c = math.floor(chan * 255 + 0.5)
        digit2 = int(c % 16)
        digit1 = int((c - digit2) / 16)

        h += HEX_CHARS[digit1] + HEX_CHARS[digit2]
    return h


def hex_to_rgb(hex_):
    hex_ = hex_.lower()
    ret = []
    _g = 0
    while _g < 3:
        i = _g
        _g = _g + 1
        index = i * 2 + 1
        _hx_str = hex_[index]
        digit1 = HEX_CHARS.find(_hx_str)
        index1 = i * 2 + 2
        str1 = hex_[index1]
        digit2 = HEX_CHARS.find(str1)
        n = digit1 * 16 + digit2
        ret.append(n / 255.0)
    return ret


def lch_to_rgb(_hx_tuple):
    return xyz_to_rgb(luv_to_xyz(lch_to_luv(_hx_tuple)))


def rgb_to_lch(_hx_tuple):
    return luv_to_lch(xyz_to_luv(rgb_to_xyz(_hx_tuple)))


def hsluv_to_rgb(_hx_tuple):
    return lch_to_rgb(hsluv_to_lch(_hx_tuple))


def rgb_to_hsluv(_hx_tuple):
    return lch_to_hsluv(rgb_to_lch(_hx_tuple))


def hpluv_to_rgb(_hx_tuple):
    return lch_to_rgb(hpluv_to_lch(_hx_tuple))


def rgb_to_hpluv(_hx_tuple):
    return lch_to_hpluv(rgb_to_lch(_hx_tuple))


def hsluv_to_hex(_hx_tuple):
    return rgb_to_hex(hsluv_to_rgb(_hx_tuple))


def hpluv_to_hex(_hx_tuple):
    return rgb_to_hex(hpluv_to_rgb(_hx_tuple))


def hex_to_hsluv(s):
    return rgb_to_hsluv(hex_to_rgb(s))


def hex_to_hpluv(s):
    return rgb_to_hpluv(hex_to_rgb(s))
