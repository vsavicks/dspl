#!/usr/bin/python2.4
#
# Copyright 2011, Google Inc.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met:
#
#    * Redistributions of source code must retain the above copyright
# notice, this list of conditions and the following disclaimer.
#    * Redistributions in binary form must reproduce the above
# copyright notice, this list of conditions and the following disclaimer
# in the documentation and/or other materials provided with the
# distribution.
#    * Neither the name of Google Inc. nor the names of its
# contributors may be used to endorse or promote products derived from
# this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

"""Objects for interacting with data sources.

The abstract DataSource class can be extended to implement an actual
data source. The other classes and functions in the module serve to aid data
sources (e.g., by guessing data types) or facilitate communication with them.
"""


__author__ = 'Benjamin Yolken <yolken@google.com>'

import re


class DataSourceError(Exception):
  """Base class for exceptions in this module."""
  pass


class DataSourceWarning(Warning):
  """Base class for warnings in this module."""
  pass


def GuessDataType(value):
  """Guess the DSPL data type of the argument string.

  Defaults to 'string' if value is not an obvious integer, float, or date.
  Also, does not try to detect boolean values, which are unlikely to be used
  in DSPL tables.

  TODO(yolken): Make this guessing more sophisticated.

  Args:
    value: A string to be evaluated.

  Returns:
    One of {'date', 'integer', 'float', 'string'}
  """
  stripped_value = value.strip().replace('"', '')

  if re.search('^-?[0-9]+$', stripped_value):
    return 'integer'
  elif re.search('^-?[0-9]+\.[0-9]+$', stripped_value):
    return 'float'
  elif re.search('^[0-9]+(/|-)[0-9]+((/|-)[0-9]+){0,1}$', stripped_value):
    return 'date'
  else:
    return 'string'


def GuessDateFormat(value):
  """Guess the Joda datetime format for the given date string.

  Supports dates like '1980', '02/1980', '1980/02, '05/02/1980', and
  '1980/05/02', separated by either slashes or hyphens. Other
  formats will cause an exception to be raised.

  TODO(yolken): Make this guessing more sophisticated.

  Args:
    value: A string containing a date

  Returns:
    A string representing the most likely Joda datetime format

  Raises:
    DataSourceError: If the format can't be figured out
  """
  stripped_value = value.strip().replace('"', '')

  year_match = re.search('^[0-9]{4}$', stripped_value)
  if year_match:
    return 'yyyy'

  month_year_match = re.search(
      '^[0-9]{1,2}(?P<separator>/|-)[0-9]{4}$', stripped_value)
  if month_year_match:
    return 'MM%syyyy' % month_year_match.groupdict()['separator']

  year_month_match = re.search(
      '^[0-9]{4}(?P<separator>/|-)[0-9]{1,2}$', stripped_value)
  if year_month_match:
    return 'yyyy%sMM' % year_month_match.groupdict()['separator']

  month_day_year_match = re.search(
      '^[0-9]{1,2}(?P<separator>/|-)'
      '[0-9]{1,2}(?P=separator)[0-9]{4}$', stripped_value)
  if month_day_year_match:
    return 'MM%sdd%syyyy' % (
        month_day_year_match.groupdict()['separator'],
        month_day_year_match.groupdict()['separator'])

  year_month_day_match = re.search(
      '^[0-9]{4}(?P<separator>/|-)'
      '[0-9]{1,2}(?P=separator)[0-9]{1,2}$', stripped_value)
  if year_month_day_match:
    return 'yyyy%sMM%sdd' % (
        year_month_day_match.groupdict()['separator'],
        year_month_day_match.groupdict()['separator'])

  raise DataSourceError(
      'Can\'t figure out date format for value: %s' % stripped_value)


def GuessDateConcept(data_format):
  """Guess the canonical time concept matching the argument datetime format.

  Args:
    data_format: A string containing a Joda datetime format

  Returns:
    One of {'time:year', 'time:month', 'time:day'}

  Raises:
    DataSourceError: If the date type isn't understood
  """
  stripped_format = data_format.strip()

  if re.search('^y+$', stripped_format):
    return 'time:year'
  elif re.search('^([yM]|[^a-zA-Z0-9])+$', stripped_format):
    return 'time:month'
  elif re.search('^([yMd]|[^a-zA-Z0-9])+$', stripped_format):
    return 'time:day'
  else:
    raise DataSourceError(
        'Can\'t figure out time concept for format: %s' % data_format)


class DataSourceColumnBundle(object):
  """Object representing an ordered collection of data source columns."""

  def __init__(self, columns=()):
    """Create a new DataSourceColumnBundle object.

    Args:
      columns: Sequence of DataSourceColumn objects
    """
    self.columns = list(columns)

    # Create internal dictionary for faster access
    self.column_dict = {}

    for column in self.columns:
      self.column_dict[column.column_id] = column

  def AddColumn(self, column):
    """Add a new Column object to the collection."""
    self.columns.append(column)
    self.column_dict[column.column_id] = column

  def GetColumnByID(self, column_id):
    """Get the Column object with the argument id string."""
    return self.column_dict[column_id]

  def GetColumnByOrder(self, column_order):
    """Get the column that is the argument number in the sequence."""
    return self.columns[column_order]

  def GetColumnIterator(self):
    """Create an iterator that loops over all the columns in the bundle."""
    return self.columns.__iter__()

  def GetNumColumns(self):
    """Get the number of Column objects in this bundle."""
    return len(self.columns)


class DataSourceColumn(object):
  """Represents a column in a data source.

  Stores a number of column-specific properties that are useful when
  generating DSPL from the data source supplying the column.
  """

  def __init__(
      self, column_id, data_type='', data_format='', concept_ref='',
      concept_extension='', slice_role='', rollup=False,
      internal_parameters=None):
    """Create a DataSourceColumn object.

    All arguments with the exception of column_id are optional.

    Args:
      column_id: Unique string identifier for this column
      data_type: DSPL data type for the column
      data_format: String representing format (used for dates only)
      concept_ref: String ID of a canonical concept that maps to this column's
                   data
      concept_extension: String ID of a canonical concept that the concept
                         for this column will extend; mutually exclusive with
                         concept_ref
      slice_role: One of {'dimension', 'metric'}
      rollup: Whether this column should be aggregated away when generating
                slices
      internal_parameters: An object (e.g. dictionary or string) that can be
                           used by the data source for storing other, private
                           parameters
    """
    self.column_id = column_id
    self.data_type = data_type
    self.data_format = data_format
    self.concept_ref = concept_ref
    self.concept_extension = concept_extension
    self.slice_role = slice_role
    self.rollup = rollup
    self.internal_parameters = internal_parameters


class QueryParameters(object):
  """Object for passing query parameters to data source."""

  def __init__(self, column_ids=()):
    """Create a new QueryParameters object.

    Just supports standard slice queries for now, i.e. getting the table
    for a combination of dimensions and metrics. May be extended in the future
    to support more query customization.

    Args:
      column_ids: Sequence of string column IDs
    """
    self.column_ids = tuple(column_ids)


class TableData(object):
  """Container for tabular data rows returned by a data source."""

  def __init__(self, rows=()):
    """Create a new TableData object.

    Args:
      rows: Sequence of sequences, each containing the values for a single row
    """
    self.rows = list(rows)

  def MergeValues(self, join_source):
    """Horizontally merge this object with another TableData object.

    Args:
      join_source: A TableData object with the same number of rows as this
                   one

    Returns:
      This TableData object
    """
    assert len(self.rows) == len(join_source.rows)

    for r, row in enumerate(self.rows):
      self.rows[r] = row + join_source.rows[r]

    return self

  def MergeConstant(self, constant_value):
    """Append the argument value to each row in this TableData object.

    Args:
      constant_value: An object to append to each row

    Returns:
      This TableData object
    """
    for r, row in enumerate(self.rows):
      self.rows[r] = row + [constant_value]

    return self


class DataSource(object):
  """An abstract representation of a DSPL data source."""

  def __init__(self, data_source_identifier, verbose=True):
    """Create a new DataSource object using the argument identifier.

    Args:
      data_source_identifier: An object used to identify the data source (e.g.,
                              string path to CSV file, URL, etc.)
      verbose: Print out status messages to stdout
    """
    pass

  def GetColumnBundle(self):
    """Get the column bundle associated with this data source.

    Returns:
      A ColumnBundle object
    """
    raise NotImplementedError('Implement this')

  def GetTableData(self, query_parameters):
    """Create a materialized data table given the argument parameters.

    Args:
      query_parameters: A QueryParameters object

    Returns:
      A TableData object.
    """
    raise NotImplementedError('Implement this')

  def Close(self):
    """Close this data source."""
    raise NotImplementedError('Implement this')