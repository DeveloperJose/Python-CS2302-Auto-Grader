# Examples with Python list problems
import numpy as np
def are_lists_ints():
    '''Example 1: Problem with no parameters and simple output'''
    return type(list) == type(int)

def has_items(L):
    '''Example 2: Problem with 1 parameter and simple output'''
    return len(L) > 0

def has_k(L, k):
    '''Example 3: Problem with 2 parameters and simple output'''
    return k in L

def generate_list_with_million_items():
    '''Example 4: Problem with no parameter and hard to visualize output'''
    return list(np.range(1_000_000))