import json
import numpy as np
import datetime
from typing import Any
from typing import Any, List, Dict, Union, Optional

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False


class EnhancedJSONEncoder(json.JSONEncoder):
    """
    Enhanced JSON encoder that handles NumPy arrays, dates, and other special types.
    """
    def default(self, obj: Any) -> Any:
        # Handle NumPy arrays
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        
        # Handle NumPy scalar types
        if isinstance(obj, (np.integer, np.int_, np.intc, np.intp, np.int8,
                           np.int16, np.int32, np.int64, np.uint8,
                           np.uint16, np.uint32, np.uint64)):
            return int(obj)
        
        if isinstance(obj, (np.float_, np.float16, np.float32, np.float64)):
            return float(obj)
        
        if isinstance(obj, (bool, bool)):
            return bool(obj)
        
        if isinstance(obj, np.complex_):
            return {"real": obj.real, "imag": obj.imag}
        
        # Handle datetime objects
        if isinstance(obj, (datetime.datetime, datetime.date)):
            return obj.isoformat()
        
        # Handle sets
        if isinstance(obj, set):
            return list(obj)
        
        # Use default JSON encoder for other types
        return super().default(obj)

def json_dumps(obj: Any) -> str:
    """
    Serialize obj to a JSON formatted str using the enhanced encoder.
    """
    return json.dumps(obj, cls=EnhancedJSONEncoder)

def json_loads(s: str) -> Any:
    """
    Deserialize s to a Python object.
    """
    return json.loads(s)

def ensure_serializable(obj: Any) -> Any:
    """
    Ensure that an object is JSON serializable by converting non-serializable types.
    """
    if isinstance(obj, (list, tuple)):
        return [ensure_serializable(item) for item in obj]
    elif isinstance(obj, dict):
        return {key: ensure_serializable(value) for key, value in obj.items()}
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, (np.integer, np.int_, np.intc, np.intp, np.int8,
                        np.int16, np.int32, np.int64, np.uint8,
                        np.uint16, np.uint32, np.uint64)):
        return int(obj)
    elif isinstance(obj, (np.float_, np.float16, np.float32, np.float64)):
        return float(obj)
    elif isinstance(obj, (bool, bool)):
        return bool(obj)
    elif isinstance(obj, (datetime.datetime, datetime.date)):
        return obj.isoformat()
    elif isinstance(obj, set):
        return list(obj)
    else:
        return obj

def safe_altair_chart(chart, use_container_width=True):
    """
    Safely render an Altair chart by ensuring all data is serializable.
    """
    import streamlit as st
    import altair as alt
    
    # Get the JSON spec from the chart
    if hasattr(chart, 'to_dict'):
        spec = chart.to_dict()
    else:
        spec = chart
    
    # Make the spec serializable
    serializable_spec = ensure_serializable(spec)
    
    # Create a new chart from the serializable spec
    safe_chart = alt.Chart.from_dict(serializable_spec)
    
    # Render the chart
    return st.altair_chart(safe_chart, use_container_width=use_container_width)

class AnomalyJSONEncoder(json.JSONEncoder):
    """
    Enhanced JSON encoder that handles NumPy arrays, dates, and other special types.
    """
    def default(self, obj: Any) -> Any:
        # Handle NumPy arrays and types if NumPy is available
        if NUMPY_AVAILABLE:
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            
            # Handle NumPy scalar types
            if isinstance(obj, (np.integer, np.int_, np.intc, np.intp, np.int8,
                            np.int16, np.int32, np.int64, np.uint8,
                            np.uint16, np.uint32, np.uint64)):
                return int(obj)
            
            if isinstance(obj, (np.float_, np.float16, np.float32, np.float64)):
                return float(obj)
            
            if isinstance(obj, (bool, bool)):
                return bool(obj)
            
            if isinstance(obj, np.complex_):
                return {"real": obj.real, "imag": obj.imag}
        
        # Handle datetime objects
        if isinstance(obj, (datetime.datetime, datetime.date)):
            return obj.isoformat()
        
        # Handle sets
        if isinstance(obj, set):
            return list(obj)
        
        # Use default JSON encoder for other types
        return super().default(obj)

def anomaly_json_dumps(obj: Any) -> str:
    """
    Serialize obj to a JSON formatted str using the enhanced encoder.
    
    Args:
        obj: Object to serialize
        
    Returns:
        JSON formatted string
    """
    return json.dumps(obj, cls=AnomalyJSONEncoder)

def anomaly_json_loads(s: str) -> Any:
    """
    Deserialize s (a str, bytes or bytearray instance containing a JSON document)
    to a Python object.
    
    Args:
        s: JSON string to deserialize
        
    Returns:
        Python object
    """
    return json.loads(s)

def anomaly_ensure_serializable(obj: Any) -> Any:
    """
    Ensure that an object is JSON serializable by converting non-serializable types.
    
    Args:
        obj: Object to make serializable
        
    Returns:
        JSON serializable object
    """
    # Handle NumPy types if NumPy is available
    if NUMPY_AVAILABLE:
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        
        if isinstance(obj, (np.integer, np.int_, np.intc, np.intp, np.int8,
                          np.int16, np.int32, np.int64, np.uint8,
                          np.uint16, np.uint32, np.uint64)):
            return int(obj)
        
        if isinstance(obj, (np.float_, np.float16, np.float32, np.float64)):
            return float(obj)
        
        if isinstance(obj, (bool, bool)):
            return bool(obj)
    
    # Handle container types recursively
    if isinstance(obj, (list, tuple)):
        return [anomaly_ensure_serializable(item) for item in obj]
    
    if isinstance(obj, dict):
        return {key: anomaly_ensure_serializable(value) for key, value in obj.items()}
    
    # Handle datetime objects
    if isinstance(obj, (datetime.datetime, datetime.date)):
        return obj.isoformat()
    
    # Handle sets
    if isinstance(obj, set):
        return list(obj)
    
    # Return other types as is
    return obj

def anomaly_safe_altair_chart(chart, use_container_width=True):
    """
    Safely render an Altair chart by ensuring all data is serializable.
    
    Args:
        chart: Altair chart to render
        use_container_width: Whether to use container width
        
    Returns:
        Rendered chart
    """
    import streamlit as st
    import altair as alt
    
    # Get the JSON spec from the chart
    if hasattr(chart, 'to_dict'):
        spec = chart.to_dict()
    else:
        spec = chart
    
    # Make the spec serializable
    serializable_spec = anomaly_ensure_serializable(spec)
    
    # Create a new chart from the serializable spec
    safe_chart = alt.Chart.from_dict(serializable_spec)
    
    # Render the chart
    return st.altair_chart(safe_chart, use_container_width=use_container_width)