import inspect
import itertools
import functools


def generate_custom_comparer(equality_fn):
    def decorator(func):
        assert callable(equality_fn), f'[Debug] Error while annotating function "{func.__name__}" [{equality_fn} must be a function]'
        # TODO: Check that the parameter count matches the one used in grader

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        wrapper.equality_fn = equality_fn
        return wrapper
    return decorator


def generate_class(__trials_per_instance__, **class_kwargs):

    def __gen_class_params__():
        params = {}
        for k_name, k_fn in class_kwargs.items():
            params[k_name] = k_fn()
        return params

    def decorator(func):
        assert type(__trials_per_instance__) == int, f'[Debug] Error while annotating class function "{func.__name__}" [{__trials_per_instance__} must be an int]'
        for k_name, k_val in class_kwargs.items():
            assert callable(k_val), f'[Debug] Error while annotating class function "{func.__name__}" ["{k_name}" has to be a function, did you forget to include lambda?]'

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        wrapper.trials_per_instance = __trials_per_instance__
        wrapper.class_kwargs = class_kwargs
        wrapper.gen_class_params = __gen_class_params__
        return wrapper
    return decorator


def generate_test_case(__trials__=2500, **fn_kwargs):

    def __gen_fn_params__():
        params = {}
        for k_name, k_fn in fn_kwargs.items():
            params[k_name] = k_fn()
        return params

    def decorator(func):
        assert type(__trials__) == int, f'[Debug] Error while annotating function "{func.__name__}" [{__trials__} must be an int]'
        assert __trials__ > 0, f'[Debug] Error while annotating function "{func.__name__}" [{__trials__} must be greater than 0]'
        for k_name, k_fn in fn_kwargs.items():
            assert callable(k_fn), f'[Debug] Error while annotating function "{func.__name__}" ["{k_name}" has to be a function, did you forget to include lambda?]'

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        wrapper.max_trials = __trials__
        wrapper.fn_kwargs = fn_kwargs
        wrapper.gen_fn_params = __gen_fn_params__
        wrapper.param_names = inspect.getargspec(func)[0]
        return wrapper
    return decorator

def set_test_case(**set_kwargs):

    def decorator(func):
        max_trials = 1
        for k_name, k_data in set_kwargs.items():
            assert isinstance(k_data, tuple), f'[Debug] Error while annotating function "{func.__name__}" ["{k_name}" has to be a tuple]'
            max_trials *= len(k_data)

        assert max_trials > 1, f'[Debug] Error while annotating function "{func.__name__}" [Tuples must be populated]'
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        params = []
        param_names = inspect.getargspec(func)[0]
        for parameter_tuple in tuple(itertools.product(*set_kwargs.values())):
            D = {}
            for (param_value, param_name) in zip(parameter_tuple, param_names):
                D[param_name] = param_value

            params.append(D)

        wrapper.max_trials = max_trials
        wrapper.set_fn_params = params
        wrapper.param_names = param_names
        return wrapper
    return decorator


def no_test_cases():
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        wrapper.no_test_cases = True
        return wrapper
    return decorator
