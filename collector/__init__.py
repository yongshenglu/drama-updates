"""Collectors for the four mainland China video platforms."""
from . import iqiyi, mgtv, tencent, youku  # noqa: F401

COLLECTORS = {
    "iqiyi": ("爱奇艺", iqiyi.collect),
    "youku": ("优酷", youku.collect),
    "tencent": ("腾讯视频", tencent.collect),
    "mgtv": ("芒果TV", mgtv.collect),
}

ORDER = ["iqiyi", "youku", "tencent", "mgtv"]
