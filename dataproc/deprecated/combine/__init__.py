#
# dataproc.combine - Data Combine Data processing routines
#
# Copyright (C) 2013 Patricio Rojo
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of version 2 of the GNU General 
# Public License as published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, 
# Boston, MA  02110-1301, USA.
#
#
"""
Data proc docstring: combine
"""


import types

modules = ['combine']
           
__all__ = []
for modulename in modules:
    module = __import__(modulename, globals(), locals(), [], -1)
    module = reload(module)
    for v in dir(module):
        if v[0] == '_' or isinstance(getattr(module,v), types.ModuleType):
            continue
        __all__.append(v)
        globals()[v] = getattr(module, v)
    del module

del modules, modulename, types



