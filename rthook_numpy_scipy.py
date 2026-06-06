# rthook_numpy_scipy.py
# PyInstaller runtime hook：在任何模块加载前强制预导入 numpy/scipy，
# 解决 scipy._lib.array_api_compat 在冻结环境中 "from numpy import *" 失败的问题。

import numpy
import numpy.fft
import numpy.linalg
import numpy.random
import numpy.ma
import numpy.lib
import numpy.core

# 触发 scipy 内部的 array_api_compat 初始化
try:
    import scipy
    import scipy._lib.array_api_compat
    import scipy._lib.array_api_compat.numpy
    import scipy._lib.array_api_compat._internal
    import scipy.signal
except Exception:
    pass
