# Bubble up our backup tasks, for easier importation

from stockpiler.tasks.stockpile.stockpile_base import StockpileResults
from stockpiler.tasks.stockpile.stockpile_cisco import stockpile_cisco_asa, stockpile_cisco_generic
