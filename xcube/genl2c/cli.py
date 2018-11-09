# The MIT License (MIT)
# Copyright (c) 2018 by the xcube development team and contributors
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in
# the Software without restriction, including without limitation the rights to
# use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies
# of the Software, and to permit persons to whom the Software is furnished to do
# so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import argparse
import sys
import traceback
from typing import List, Optional

from xcube.dsio import query_dataset_io
from xcube.genl2c.config import get_config_dict
from xcube.genl2c.defaults import DEFAULT_OUTPUT_DIR, DEFAULT_OUTPUT_NAME, \
    DEFAULT_OUTPUT_RESAMPLING, DEFAULT_OUTPUT_WRITER
from xcube.genl2c.inputprocessor import InputProcessor
from xcube.genl2c.process import generate_l2c_cube
from xcube.objreg import get_obj_registry
from xcube.reproject import NAME_TO_GDAL_RESAMPLE_ALG
from xcube.version import version


def main(args: Optional[List[str]] = None):
    """
    Generate L2C data cubes from L2 data products.
    """
    input_processor_names = [input_processor.name
                             for input_processor in get_obj_registry().get_all(type=InputProcessor)]
    output_writer_names = [ds_io.name for ds_io in query_dataset_io(lambda ds_io: 'w' in ds_io.modes)]
    resampling_algs = NAME_TO_GDAL_RESAMPLE_ALG.keys()

    parser = argparse.ArgumentParser(description='Generate or extend a Level-2C data cube from Level-2 input files. '
                                                 'Level-2C data cubes may be created in one go or in successively '
                                                 'in append mode, input by input.',
                                     formatter_class=GenL2CHelpFormatter)
    parser.add_argument('--version', '-V', action='version', version=version)
    parser.add_argument('--proc', '-p', dest='input_processor', choices=input_processor_names,
                        help=f'Input processor type name.')
    parser.add_argument('--config', '-c', dest='config_file',
                        help='Data cube configuration file in YAML format.')
    parser.add_argument('--dir', '-d', dest='output_dir',
                        help=f'Output directory. Defaults to {DEFAULT_OUTPUT_DIR!r}')
    parser.add_argument('--name', '-n', dest='output_name',
                        help=f'Output filename pattern. Defaults to {DEFAULT_OUTPUT_NAME!r}.')
    parser.add_argument('--writer', '-w', dest='output_writer', choices=output_writer_names,
                        help=f'Output writer type name. Defaults to {DEFAULT_OUTPUT_WRITER!r}.')
    parser.add_argument('--size', '-s', dest='output_size',
                        help='Output size in pixels using format "<width>,<height>".')
    parser.add_argument('--region', '-r', dest='output_region',
                        help='Output region using format "<lon-min>,<lat-min>,<lon-max>,<lat-max>"')
    parser.add_argument('--vars', '-v', dest='output_variables',
                        help='Variables to be included in output. '
                             'Comma-separated list of names which may contain wildcard characters "*" and "?".')
    parser.add_argument('--resamp', dest='output_resampling', choices=resampling_algs,
                        help='Fallback spatial resampling algorithm to be used for all variables.'
                             f'Defaults to {DEFAULT_OUTPUT_RESAMPLING!r}.')
    parser.add_argument('--traceback', dest='traceback_mode', default=False, action='store_true',
                        help='On error, print Python traceback.')
    parser.add_argument('--append', '-a', dest='append_mode', default=False, action='store_true',
                        help='Append successive outputs.')
    parser.add_argument('--dry-run', default=False, action='store_true',
                        help='Just read and process inputs, but don\'t produce any outputs.')
    parser.add_argument('input_files', metavar='INPUT_FILES', nargs='+',
                        help="One or more input files or a pattern that may contain wildcards '?', '*', and '**'.")

    try:
        arg_obj = parser.parse_args(args or sys.argv[1:])
    except SystemExit as e:
        return int(str(e))

    traceback_mode = arg_obj.traceback_mode
    append_mode = arg_obj.append_mode
    dry_run = arg_obj.dry_run

    try:
        config = get_config_dict(arg_obj, open)
    except ValueError as e:
        return _handle_error(e, traceback_mode)

    # noinspection PyBroadException
    try:
        generate_l2c_cube(append_mode=append_mode,
                          dry_run=dry_run,
                          monitor=print,
                          **config)
    except Exception as e:
        return _handle_error(e, traceback_mode)

    return 0


def _handle_error(e, traceback_mode):
    print(f'error: {e}', file=sys.stderr)
    if traceback_mode:
        traceback.print_exc(file=sys.stderr)
    return 2


class GenL2CHelpFormatter(argparse.HelpFormatter):

    def format_help(self):
        # noinspection PyUnresolvedReferences
        help_text = super().format_help()

        input_processors = get_obj_registry().get_all(type=InputProcessor)
        output_writers = query_dataset_io(lambda ds_io: 'w' in ds_io.modes)

        help_text += '\ninput processors to be used with option --proc:\n'
        help_text += self._format_input_processors(input_processors)
        help_text += '\noutput formats to be used with option --writer:\n'
        help_text += self._format_dataset_ios(output_writers)
        help_text += '\n'

        return help_text

    @classmethod
    def _format_input_processors(cls, input_processors):
        help_text = ''
        for input_processor in input_processors:
            fill = ' ' * (34 - len(input_processor.name))
            help_text += f'  {input_processor.name}{fill}{input_processor.description}\n'
        return help_text

    @classmethod
    def _format_dataset_ios(cls, dataset_ios):
        help_text = ''
        for ds_io in dataset_ios:
            fill1 = ' ' * (24 - len(ds_io.name))
            fill2 = ' ' * (10 - len(ds_io.ext))
            help_text += f'  {ds_io.name}{fill1}(*.{ds_io.ext}){fill2}{ds_io.description}\n'
        return help_text


if __name__ == '__main__':
    sys.exit(main())
