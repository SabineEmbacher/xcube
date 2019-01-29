from contextlib import contextmanager
from typing import Dict, List, Union, Tuple, Any, Optional

import numpy as np
import pandas as pd
import xarray as xr

from xcube.dsio import find_dataset_io, guess_dataset_format, FORMAT_NAME_ZARR, FORMAT_NAME_NETCDF4

_TIME_DTYPE = "datetime64[s]"
_TIME_UNITS = "seconds since 1970-01-01T00:00:00"
_TIME_CALENDAR = "proleptic_gregorian"


def new_cube(title="Test Cube",
             width=360,
             height=180,
             spatial_res=1.0,
             lon_start=-180.0,
             lat_start=-90.0,
             time_periods=5,
             time_freq="D",
             time_start='2010-01-01T00:00:00',
             drop_bounds=False,
             variables=None):
    """
    Create a new empty cube. Useful for testing.

    :param title: A title.
    :param width: Horizontal number of grid cells
    :param height: Vertical number of grid cells
    :param spatial_res: Spatial resolution in degrees
    :param lon_start: Minimum longitude value
    :param lat_start: Minimum latitude value
    :param time_periods: Number of time steps
    :param time_freq: Duration of each time step
    :param time_start: First time value
    :param drop_bounds: If True, coordinate bounds variables are not created.
    :param variables: Dictionary of data variables to be added.
    :return: A cube instance
    """
    lon_end = lon_start + width * spatial_res
    lat_end = lat_start + height * spatial_res
    if width < 0 or height < 0 or spatial_res <= 0.0:
        raise ValueError()
    if lon_start < -180. or lon_end > 180. or lat_start < -90. or lat_end > 90.:
        raise ValueError()
    if time_periods < 0:
        raise ValueError()

    lon_data = np.linspace(lon_start + 0.5 * spatial_res, lon_end - 0.5 * spatial_res, width)
    lon = xr.DataArray(lon_data, dims="lon")
    lon.attrs["units"] = "degrees_east"

    lat_data = np.linspace(lat_start + 0.5 * spatial_res, lat_end - 0.5 * spatial_res, height)
    lat = xr.DataArray(lat_data, dims="lat")
    lat.attrs["units"] = "degrees_north"

    time_data_2 = pd.date_range(start=time_start, periods=time_periods + 1, freq=time_freq).values
    time_data_2 = time_data_2.astype(dtype=_TIME_DTYPE)
    time_delta = time_data_2[1] - time_data_2[0]
    time_data = time_data_2[0:-1] + time_delta // 2
    time = xr.DataArray(time_data, dims="time")
    time.encoding["units"] = _TIME_UNITS
    time.encoding["calendar"] = _TIME_CALENDAR

    time_data_2 = pd.date_range(time_start, periods=time_periods + 1, freq=time_freq)

    coords = dict(lon=lon, lat=lat, time=time)
    if not drop_bounds:
        lon_bnds_data = np.zeros((width, 2), dtype=np.float64)
        lon_bnds_data[:, 0] = np.linspace(lon_start, lon_end - spatial_res, width)
        lon_bnds_data[:, 1] = np.linspace(lon_start + spatial_res, lon_end, width)
        lon_bnds = xr.DataArray(lon_bnds_data, dims=("lon", "bnds"))
        lon_bnds.attrs["units"] = "degrees_east"

        lat_bnds_data = np.zeros((height, 2), dtype=np.float64)
        lat_bnds_data[:, 0] = np.linspace(lat_start, lat_end - spatial_res, height)
        lat_bnds_data[:, 1] = np.linspace(lat_start + spatial_res, lat_end, height)
        lat_bnds = xr.DataArray(lat_bnds_data, dims=("lat", "bnds"))
        lat_bnds.attrs["units"] = "degrees_north"

        time_bnds_data = np.zeros((time_periods, 2), dtype="datetime64[ns]")
        time_bnds_data[:, 0] = time_data_2[:-1]
        time_bnds_data[:, 1] = time_data_2[1:]
        time_bnds = xr.DataArray(time_bnds_data, dims=("time", "bnds"))
        time_bnds.encoding["units"] = _TIME_UNITS
        time_bnds.encoding["calendar"] = _TIME_CALENDAR

        lon.attrs["bounds"] = "lon_bnds"
        lat.attrs["bounds"] = "lat_bnds"
        time.attrs["bounds"] = "time_bnds"

        coords.update(dict(lon_bnds=lon_bnds, lat_bnds=lat_bnds, time_bnds=time_bnds))

    attrs = {
        "Conventions": "CF-1.7",
        "title": title,
        "time_coverage_start": str(time_data_2[0]),
        "time_coverage_end": str(time_data_2[-1]),
        "geospatial_lon_min": lon_start,
        "geospatial_lon_max": lon_end,
        "geospatial_lon_units": "degrees_east",
        "geospatial_lat_min": lat_start,
        "geospatial_lat_max": lat_end,
        "geospatial_lat_units": "degrees_north",
    }

    data_vars = {}
    if variables:
        dims = ("time", "lat", "lon")
        shape = (time_periods, height, width)
        size = time_periods * height * width
        for var_name, data in variables.items():
            if isinstance(data, xr.DataArray):
                data_vars[var_name] = data
            elif isinstance(data, int) or isinstance(data, float) or isinstance(data, bool):
                data_vars[var_name] = xr.DataArray(np.full(shape, data), dims=dims)
            elif data is None:
                data_vars[var_name] = xr.DataArray(np.random.uniform(0.0, 1.0, size).reshape(shape), dims=dims)
            else:
                data_vars[var_name] = xr.DataArray(data, dims=dims)

    return xr.Dataset(data_vars=data_vars, coords=coords, attrs=attrs)


@contextmanager
def open_dataset(input_path: str,
                 format_name: str = None,
                 **kwargs) -> xr.Dataset:
    """
    The ``read_dataset`` function as context manager that auto-closes the dataset read.

    :param input_path: input path
    :param format_name: format, e.g. "zarr" or "netcdf4"
    :param kwargs: format-specific keyword arguments
    :return: dataset object
    """
    dataset = read_dataset(input_path, format_name, **kwargs)
    try:
        yield dataset
    finally:
        dataset.close()


def read_dataset(input_path: str,
                 format_name: str = None,
                 **kwargs) -> xr.Dataset:
    """
    Read a dataset.

    :param input_path: input path
    :param format_name: format, e.g. "zarr" or "netcdf4"
    :param kwargs: format-specific keyword arguments
    :return: dataset object
    """
    format_name = format_name if format_name else guess_dataset_format(input_path)
    if format_name is None:
        raise ValueError("Unknown input format")
    dataset_io = find_dataset_io(format_name, modes=["r"])
    if dataset_io is None:
        raise ValueError(f"Unknown input format {format_name!r} for {input_path}")

    return dataset_io.read(input_path, **kwargs)


def write_dataset(dataset: xr.Dataset,
                  output_path: str,
                  format_name: str = None,
                  **kwargs) -> xr.Dataset:
    """
    Write dataset.

    :param dataset: Dataset to be written.
    :param output_path: output path
    :param format_name: format, e.g. "zarr" or "netcdf4"
    :param kwargs: format-specific keyword arguments
    :return: the input dataset
    """
    format_name = format_name if format_name else guess_dataset_format(output_path)
    if format_name is None:
        raise ValueError("Unknown output format")
    dataset_io = find_dataset_io(format_name, modes=["w"])
    if dataset_io is None:
        raise ValueError(f"Unknown output format {format_name!r} for {output_path}")

    dataset_io.write(dataset, output_path, **kwargs)

    return dataset


def chunk_dataset(dataset: xr.Dataset,
                  chunk_sizes: Dict[str, int] = None,
                  format_name: str = None) -> xr.Dataset:
    """
    Chunk dataset and update encodings for given format.

    :param dataset: input dataset
    :param chunk_sizes: mapping from dimension name to new chunk size
    :param format_name: format, e.g. "zarr" or "netcdf4"
    :return: the re-chunked dataset
    """
    chunked_ds = dataset.chunk(chunks=chunk_sizes)

    # Update encoding so writing of chunked_ds recognizes new chunks
    chunk_sizes_attr_name = None
    if format_name == FORMAT_NAME_ZARR:
        chunk_sizes_attr_name = "chunks"
    if format_name == FORMAT_NAME_NETCDF4:
        chunk_sizes_attr_name = "chunksizes"
    if chunk_sizes_attr_name:
        for var_name in chunked_ds.variables:
            var = chunked_ds[var_name]
            if chunk_sizes:
                sizes = tuple(chunk_sizes[dim_name] if dim_name in chunk_sizes
                              else var.shape[var.dims.index(dim_name)]
                              for dim_name in var.dims)
                var.encoding.update({chunk_sizes_attr_name: sizes})
            elif chunk_sizes_attr_name in var.encoding:
                # Remove any explicit and wrong specification so writing will use Dask chunks (TBC!)
                del var.encoding[chunk_sizes_attr_name]

    return chunked_ds


def dump_dataset(dataset: xr.Dataset,
                 variable_names=None,
                 show_var_encoding=False) -> str:
    """
    Dumps a dataset or variables into a text string.

    :param dataset: input dataset
    :param variable_names: names of variables to be dumped
    :param show_var_encoding: also dump variable encodings?
    :return: the dataset dump
    """
    lines = []
    if not variable_names:
        lines.append(str(dataset))
        if show_var_encoding:
            for var_name, var in dataset.coords.items():
                if var.encoding:
                    lines.append(dump_var_encoding(var, header=f"Encoding for coordinate variable {var_name!r}:"))
            for var_name, var in dataset.data_vars.items():
                if var.encoding:
                    lines.append(dump_var_encoding(var, header=f"Encoding for data variable {var_name!r}:"))
    else:
        for var_name in variable_names:
            var = dataset[var_name]
            lines.append(str(var))
            if show_var_encoding and var.encoding:
                lines.append(dump_var_encoding(var))
    return "\n".join(lines)


def dump_var_encoding(var: xr.DataArray, header="Encoding:", indent=4) -> str:
    """
    Dump the encoding information of a variable into a text string.

    :param var: Dataset variable.
    :param header: Title/header string.
    :param indent: Indention in spaces.
    :return: the variable dump
    """
    lines = [header]
    max_len = 0
    for k in var.encoding:
        max_len = max(max_len, len(k))
    indent_spaces = indent * " "
    for k, v in var.encoding.items():
        tab_spaces = (2 + max_len - len(k)) * " "
        lines.append(f"{indent_spaces}{k}:{tab_spaces}{v!r}")
    return "\n".join(lines)


def get_cube_values(cube: xr.Dataset,
                    indexes: pd.DataFrame,
                    include_indexes: bool = False,
                    cube_asserted: bool = False) -> pd.DataFrame:
    """
    Get values from the *cube* at given *indexes*.

    :param cube: A cube dataset.
    :param indexes: A Pandas data frame that contains the indexes for all cube dimensions.
    :param include_indexes: If True, include indexes in returned data frame.
    :param cube_asserted: If False, *cube* will be verified, otherwise it is expected to be a valid cube.
    :return: A new data frame whose columns are values from *cube* variables at given *indexes*.
    """
    if not cube_asserted:
        assert_cube(cube)

    dims = get_cube_dims(cube)
    num_dims = len(dims)
    for i in range(num_dims):
        dim_name = dims[i]
        if dim_name not in indexes:
            raise ValueError(f"missing dimension {dim_name!r} in indexes")

    chunks = get_cube_chunks(cube)
    # print(chunks)
    chunks = None

    index_arrays = []
    if chunks is not None:
        if len(chunks) != num_dims:
            raise ValueError("inconsistent cube")
        interp_arrays = _get_chunk_interp_arrays(chunks)
        chunk_index_arrays = []
        for i in range(num_dims):
            dim_name = dims[i]
            index_values = indexes[dim_name].values
            chunk_index_array = np.interp(index_values,
                                          interp_arrays[0],
                                          interp_arrays[1], left=-1, right=-1).astype(dtype=np.int64)
            chunk_index_arrays.append(chunk_index_array)
            index_arrays.append(index_values)
        # TODO (forman): sort  index_arrays by chunk_index_arrays
    else:
        for i in range(num_dims):
            dim_name = dims[i]
            index_arrays.append(indexes[dim_name].values)

    row_indexes = np.stack(index_arrays, axis=-1)
    # print(row_indexes)

    num_rows = len(row_indexes)

    vars = [cube[var_name] for var_name in cube.data_vars]
    var_names = [var_name for var_name in cube.data_vars]
    var_values = [np.ndarray((num_rows,), dtype=cube[var_name].dtype) for var_name in cube.data_vars]

    num_vars = len(var_names)

    # TODO (forman): the following loop is very slow (up to 0.5 seconds each cycle).
    # We may optimize by loading data chunk-wise and then extracting points from the loaded sub-arrays.
    # chunks = _get_var_chunks(cube)

    for i in range(num_rows):
        row_index = tuple(row_indexes[i])
        if -1 in row_index:
            for j in range(num_vars):
                var_values[j][i] = np.nan
        else:
            for j in range(num_vars):
                var_data = vars[j].data
                var_values[j][i] = var_data[row_index]

    values = pd.DataFrame({var_names[j]: var_values[j] for j in range(num_vars)})

    if include_indexes:
        values = pd.concat(values, indexes)

    return values


def get_cube_point_values(cube: xr.Dataset,
                          points: Union[pd.DataFrame, Any],
                          include_indexes: bool = False,
                          cube_asserted: bool = False) -> pd.DataFrame:
    """
    Extract values from *cube* variables at given coordinates in *points*.

    :param cube: The cube dataset.
    :param points: Dictionary that maps dimension name to coordinate arrays.
    :param include_indexes: If True, include indexes in returned data frame.
    :param cube_asserted: If False, *cube* will be verified, otherwise it is expected to be a valid cube.
    :return: A new data frame whose columns are values from *cube* variables at given *points*.
    """
    if not cube_asserted:
        assert_cube(cube)
    indexes = get_cube_point_indexes(cube, points, cube_asserted=True)
    return get_cube_values(cube, indexes, include_indexes=include_indexes, cube_asserted=True)


def get_cube_point_indexes(cube: xr.Dataset,
                           points: Union[pd.DataFrame, Any],
                           dim_name_mapping: Dict[str, str] = None,
                           cube_asserted: bool = False) -> pd.DataFrame:
    """
    Get indexes of given point coordinates *points* into the given *dataset*.

    :param cube: The cube dataset.
    :param points: A pandas data frame or object that can be converted into a Pandas DataFrame.
    :param dim_name_mapping: A mapping from dimension names in *cube* to column names in *points*.
    :param cube_asserted: If False, *cube* will be verified, otherwise it is expected to be a valid cube.
    :return: A dictionary that maps dimension names to integer index arrays.
    """
    if not cube_asserted:
        assert_cube(cube)

    if not isinstance(points, pd.DataFrame):
        points = pd.DataFrame(points)

    dim_names = _get_cube_data_var_dims(cube)

    first_col_name = None
    indexes = []
    for dim_name in dim_names:
        if dim_name not in cube.coords:
            raise ValueError(f"missing coordinate variable for dimension {dim_name!r}")
        col_name = dim_name_mapping[dim_name] if dim_name_mapping and dim_name in dim_name_mapping else dim_name
        if col_name not in points:
            raise ValueError(f"column {col_name!r} not found in points")
        dim_col = points[col_name]
        if first_col_name is None:
            first_col_name = col_name
        else:
            first_col_size = len(points[first_col_name])
            col_size = len(dim_col)
            if first_col_size != col_size:
                raise ValueError("number of point coordinates must be same for all columns,"
                                 f" but found {first_col_size} for column {first_col_name!r}"
                                 f" and {col_size} for column {col_name!r}")

        indexes.append((dim_name, get_coord_indexes(cube, dim_name, dim_col.values)))

    return pd.DataFrame(dict(indexes))


def _get_cube_data_var_dims(cube: xr.Dataset) -> Tuple[str, ...]:
    for var in cube.data_vars.values():
        return var.dims
    raise ValueError("cube dataset is empty")


def get_coord_indexes(dataset: xr.Dataset,
                      coord_var_name: str,
                      coord_values,
                      ret_fractions=False) -> Union[np.ndarray, Tuple[np.ndarray, np.ndarray]]:
    """
    Compute the indexes into a coordinate variable *coord_var_name* of a *dataset*
    for the given coordinate values *coord_values*.

    The coordinate variable's labels must be monotonic increasing, otherwise the result will be nonsense.

    For any value in *coord_values* that is out of the bounds of the coordinate variable's values,
    the index -1 will be returned.

    Returns the computed indexes as int64 array. If *ret_fractions* is True,
    a tuple of the indexes and their fractions of type float64 will be returned.

    :param dataset: A cube dataset.
    :param coord_var_name: Name of a coordinate variable.
    :param coord_values: Array-like coordinate values.
    :param ret_fractions: If true.
    :return: a numpy array of type *dtype*.
    """
    coord_var = dataset[coord_var_name]
    n1 = coord_var.size
    n2 = n1 + 1

    coord_bounds_var = _get_bounds_var(dataset, coord_var_name)
    if coord_bounds_var is not None:
        coord_bounds = coord_bounds_var.values
        if np.issubdtype(coord_bounds.dtype, np.datetime64):
            coord_bounds = coord_bounds.astype(np.uint64)
        is_reversed = (coord_bounds[0, 1] - coord_bounds[0, 0]) < 0
        if is_reversed:
            coord_bounds = coord_bounds[::-1, ::-1]
        coords = np.zeros(n2, dtype=coord_bounds.dtype)
        coords[0:-1] = coord_bounds[:, 0]
        coords[-1] = coord_bounds[-1, 1]
    elif coord_var.size > 1:
        center_coords = coord_var.values
        if np.issubdtype(center_coords.dtype, np.datetime64):
            center_coords = center_coords.astype(np.uint64)
        is_reversed = (center_coords[-1] - center_coords[0]) < 0
        if is_reversed:
            center_coords = center_coords[::-1]
        deltas = np.zeros(n2, dtype=center_coords.dtype)
        deltas[0:-2] = np.diff(center_coords)
        deltas[-2] = deltas[-3]
        deltas[-1] = deltas[-3]
        coords = np.zeros(n2, dtype=center_coords.dtype)
        coords[0:-1] = center_coords
        coords[-1] = coords[-2] + deltas[-1]
        if np.issubdtype(deltas.dtype, np.int):
            coords -= deltas // 2
        else:
            coords -= 0.5 * deltas
    else:
        raise ValueError(f"cannot determine cell boundaries for"
                         f" coordinate variable {coord_var_name!r} of size {coord_var.size}")

    if np.issubdtype(coord_values.dtype, np.datetime64):
        coord_values = coord_values.astype(np.uint64)
    x = np.linspace(0.0, n1, n2, dtype=np.float64)
    result = np.interp(coord_values, coords, x, left=-1, right=-1)
    indexes = result.astype(np.int64)
    upper_bound_hit = indexes >= n1
    indexes[upper_bound_hit] = n1 - 1
    if ret_fractions:
        fractions = result - indexes
        fractions[upper_bound_hit] = 1.0
        if is_reversed:
            indexes = indexes[::-1]
            fractions = fractions[::-1]
        return indexes, fractions
    if is_reversed:
        indexes = indexes[::-1]
    return indexes


def _get_chunk_interp_arrays(chunks: Tuple[Tuple[int, ...], ...]) -> Tuple[Tuple[np.ndarray, np.ndarray], ...]:
    coords = []
    for dim_chunks in chunks:
        n = len(dim_chunks)
        dim_indexes = np.zeros(n + 1, np.int64)
        for i in range(n):
            dim_indexes[i + 1] = dim_indexes[i] + dim_chunks[i]
        coords.append((dim_indexes, np.linspace(0, n, num=n + 1, dtype=np.int64)))
    return tuple(coords)


def get_cube_chunks(cube: xr.Dataset) -> Optional[Tuple[Tuple[int, ...], ...]]:
    """
    Get chunk sizes of the given *cube* dataset.

    The function returns the chunks of the first data variable, if any,
    because all data variables in a cube are expected to have same chunk sizes.

    :param cube: A cube dataset
    :return: A tuple of cube sizes for each cube dimension.
    """
    for var_name in cube.data_vars:
        var_data = cube[var_name].data
        return var_data.chunks if hasattr(var_data, "chunks") else None
    return None


def get_cube_dims(cube: xr.Dataset) -> Optional[Tuple[str]]:
    """
    Get dimension names of the given *cube* dataset.

    The function returns the dimensions of the first data variable, if any,
    because all data variables in a cube are expected to have same dimensions.

    :param cube: A cube dataset
    :return: A tuple of dimension names or None if the cube has no data variables.
    """
    for var_name in cube.data_vars:
        return cube[var_name].dims
    return None


def _get_bounds_var(dataset: xr.Dataset, var_name: str) -> Optional[xr.DataArray]:
    var = dataset[var_name]
    if len(var.shape) == 1:
        bounds_var_name = var.attrs.get("bounds", var_name + "_bnds")
        if bounds_var_name in dataset:
            bounds_var = dataset[bounds_var_name]
            if bounds_var.dtype == var.dtype and bounds_var.shape == (var.size, 2):
                return bounds_var
    return None


def assert_cube(dataset: xr.Dataset, name=None):
    """
    Assert that the given *dataset* is a valid data cube.

    :param dataset: The dataset to be validated.
    :param name: Optional parameter name.
    :raise: ValueError, if dataset is not a valid data cube
    """
    report = verify_cube(dataset)
    if report:
        message = f"Dataset" + (name + " " if name else " ")
        message += "is not a valid data cube, because:\n"
        message += "- " + ";\n- ".join(report) + "."
        raise ValueError(message)


def verify_cube(dataset: xr.Dataset) -> List[str]:
    """
    Verify the given *dataset* for being a valid data cube.

    Returns a list of issues, which is empty if *dataset* is a valid data cube.

    :param dataset: A dataset to be verified.
    :return: List of issues or empty list.
    """
    report = []
    _check_dim(dataset, "time", report)
    _check_dim(dataset, "lat", report)
    _check_dim(dataset, "lon", report)
    _check_time(dataset, "time", report)
    _check_lon_or_lat(dataset, "lat", -90, 90, report)
    _check_lon_or_lat(dataset, "lon", -180, 180, report)
    _check_data_variables(dataset, report)
    return report


def _check_data_variables(dataset, report):
    first_var = None
    first_dims = None
    first_chunks = None
    for var_name, var in dataset.data_vars.items():
        dims = var.dims
        chunks = var.data.chunks if hasattr(var.data, "chunks") else None

        if len(dims) < 3 or dims[0] != "time" or dims[-2] != "lat" or dims[-1] != "lon":
            report.append(f"dimensions of data variable {var_name!r}"
                          f" must be ('time', ..., 'lat', 'lon'),"
                          f" but were {dims!r} for {var_name!r}")

        if first_var is None:
            first_var = var
            first_dims = dims
            first_chunks = chunks
            continue

        if first_dims != dims:
            report.append("dimensions of all data variables must be same,"
                          f" but found {first_dims!r} for {first_var.name!r} "
                          f"and {dims!r} for {var_name!r}")

        if first_chunks != chunks:
            report.append("all data variables must have same chunk sizes,"
                          f" but found {first_chunks!r} for {first_var.name!r} "
                          f"and {chunks!r} for {var_name!r}")


def _check_dim(dataset, name, report):
    if name not in dataset.dims:
        report.append(f"missing dimension {name!r}")

    if dataset.dims[name] < 0:
        report.append(f"size of dimension {name!r} must be a positive integer")


def _check_coord_var(dataset, name, report):
    if name not in dataset.coords:
        report.append(f"missing coordinate variable {name!r}")
        return None

    var = dataset.coords[name]
    if var.dims != (name,):
        report.append(f"coordinate variable {name!r} must have a single dimension {name!r}")
        return None

    if var.size == 0:
        report.append(f"coordinate variable {name!r} must not be empty")
        return None

    return var


def _check_lon_or_lat(dataset, name, min_value, max_value, report):
    var = _check_coord_var(dataset, name, report)
    if var is None:
        return

    if not np.all(np.isfinite(var)):
        report.append(f"values of coordinate variable {name!r} must be finite")

    if np.min(var) < min_value or np.max(var) > max_value:
        report.append(f"values of coordinate variable {name!r}"
                      f" must be in the range {min_value} to {max_value}")

    # TODO (forman): the following check is not valid for "lat" because we currently use wrong lat-order
    # TODO (forman): the following check is not valid for "lon" if a cube covers the antimeridian
    # if not np.all(np.diff(var.astype(np.float64)) > 0):
    #    report.append(f"values of coordinate variable {name!r} must be monotonic increasing")


def _check_time(dataset, name, report):
    var = _check_coord_var(dataset, name, report)
    if var is None:
        return

    if not np.issubdtype(var.dtype, np.datetime64):
        report.append(f"type of coordinate variable {name!r} must be datetime64")

    if not np.all(np.diff(var.astype(np.float64)) > 0):
        report.append(f"values of coordinate variable {name!r} must be monotonic increasing")
