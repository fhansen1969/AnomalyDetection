def serialize_numpy_data(obj):
    """Convert NumPy data types to Python native types for JSON serialization.
    
    This function can be used as a default converter for json.dumps:
    json.dumps(data, default=serialize_numpy_data)
    
    Args:
        obj: The object to serialize
        
    Returns:
        The converted object (if it was a NumPy type) or the original object
    """
    import numpy as np
    from datetime import datetime
    import pandas as pd
    
    # Handle different NumPy data types
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, bool):
        return bool(obj)
    elif isinstance(obj, (np.datetime64, np.timedelta64)):
        return str(obj)
    elif isinstance(obj, (datetime, pd.Timestamp)):
        return obj.isoformat()
    elif isinstance(obj, pd.Timedelta):
        return str(obj)
    elif isinstance(obj, pd.Series):
        return obj.tolist()
    elif isinstance(obj, pd.DataFrame):
        return obj.to_dict(orient='records')
    
    # Return original object if it's not a NumPy type
    return obj

def make_dataframe_json_friendly(df):
    """Convert all NumPy data types in a DataFrame to Python native types.
    
    This makes the DataFrame safe for JSON serialization, which is needed
    for Altair charts and other visualizations.
    
    Args:
        df: A pandas DataFrame
        
    Returns:
        A copy of the DataFrame with all NumPy types converted to Python native types
    """
    import pandas as pd
    import numpy as np
    
    # Create a copy to avoid modifying the original
    df_copy = df.copy()
    
    # Function to convert NumPy types to Python native types
    def convert_numpy_types(x):
        if isinstance(x, np.integer):
            return int(x)
        elif isinstance(x, np.floating):
            return float(x)
        elif isinstance(x, np.ndarray):
            return x.tolist()
        elif isinstance(x, bool):
            return bool(x)
        elif isinstance(x, (np.datetime64, np.timedelta64)):
            return pd.Timestamp(x).isoformat()
        elif pd.isna(x):
            return None
        return x
    
    # Convert all columns
    for col in df_copy.columns:
        # Handle datetime columns specially
        if pd.api.types.is_datetime64_any_dtype(df_copy[col]):
            df_copy[col] = df_copy[col].dt.strftime('%Y-%m-%d %H:%M:%S')
        # Handle other NumPy types
        elif df_copy[col].dtype.kind in 'uifcmM':  # NumPy numeric types
            df_copy[col] = df_copy[col].apply(convert_numpy_types)
    
    return df_copy