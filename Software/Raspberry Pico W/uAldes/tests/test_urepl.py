"""
Pytest tests for urepl

Run with: pytest tests/test_urepl.py -v
"""

import pytest
import sys
import os
from unittest.mock import patch, MagicMock
import socket

# Add cli directory to path
CLI_DIR = os.path.join(os.path.dirname(__file__), '..', 'cli')
sys.path.insert(0, CLI_DIR)

from urepl import (
    TcpRepl, cmd_exec, cmd_eval, cmd_run, cmd_ls, cmd_cat,
    cmd_cp, cmd_rm, cmd_mkdir, cmd_reset, cmd_sync
)


class TestTcpReplConnection:
    """Tests for TcpRepl connection handling"""

    def test_connect_creates_socket(self):
        """Test that connect creates a socket"""
        with patch('urepl.socket.socket') as mock_socket:
            mock_sock = MagicMock()
            mock_socket.return_value = mock_sock

            repl = TcpRepl('192.168.1.1', 80)
            repl.connect()

            mock_socket.assert_called_once_with(socket.AF_INET, socket.SOCK_STREAM)
            mock_sock.connect.assert_called_once_with(('192.168.1.1', 80))

    def test_close_clears_socket(self):
        """Test that close clears the socket"""
        repl = TcpRepl('192.168.1.1', 80)
        repl.sock = MagicMock()
        repl.in_raw_mode = True

        repl.close()

        assert repl.sock is None
        assert repl.in_raw_mode is False

    def test_init_sets_defaults(self):
        """Test that __init__ sets correct defaults"""
        repl = TcpRepl('192.168.1.1')

        assert repl.host == '192.168.1.1'
        assert repl.port == 80
        assert repl.timeout == 10
        assert repl.sock is None
        assert repl.in_raw_mode is False


class TestRawReplProtocol:
    """Tests for raw REPL protocol handling"""

    @pytest.fixture
    def repl_with_mock_socket(self):
        """Create a TcpRepl with mocked socket"""
        repl = TcpRepl('192.168.1.1', 80)
        repl.sock = MagicMock()
        return repl

    def test_enter_raw_repl_sends_ctrl_a(self, repl_with_mock_socket):
        """Test that entering raw REPL sends CTRL+A"""
        repl = repl_with_mock_socket
        # _read_all clears buffer (timeout), then _read_until reads response
        repl.sock.recv.side_effect = [
            socket.timeout(),  # _read_all initial clear
            b'raw REPL; CTRL-B to exit\r\n>',  # _read_until response
        ]

        result = repl.enter_raw_repl()

        assert result is True
        repl.sock.sendall.assert_called_with(b'\x01')
        assert repl.in_raw_mode is True

    def test_exec_raw_parses_response(self, repl_with_mock_socket):
        """Test that exec_raw correctly parses OK response"""
        repl = repl_with_mock_socket
        repl.in_raw_mode = True
        # Simulate response: OK\x04<output>\x04\x04>
        repl.sock.recv.side_effect = [b'OK\x042\x04\x04>']

        output, error = repl.exec_raw('1+1')

        assert output == '2'
        assert error is None

    def test_exec_raw_handles_error(self, repl_with_mock_socket):
        """Test that exec_raw handles error responses"""
        repl = repl_with_mock_socket
        repl.in_raw_mode = True
        # Simulate response with error
        repl.sock.recv.side_effect = [b'OK\x04\x04NameError: name \'x\' is not defined\x04>']

        output, error = repl.exec_raw('x')

        assert output == ''
        assert 'NameError' in error

    def test_exec_raw_sends_code_with_ctrl_d(self, repl_with_mock_socket):
        """Test that exec_raw sends code followed by CTRL+D"""
        repl = repl_with_mock_socket
        repl.in_raw_mode = True
        repl.sock.recv.side_effect = [b'OK\x04result\x04\x04>']

        repl.exec_raw('print("hello")')

        # Check that code + CTRL_D was sent
        calls = repl.sock.sendall.call_args_list
        assert any(b'print("hello")' in call[0][0] for call in calls)
        assert any(b'\x04' in call[0][0] for call in calls)


class TestChunkedUpload:
    """Tests for chunked file upload logic"""

    def test_chunk_size_is_512(self):
        """Test chunking with 512 byte chunks"""
        content = 'x' * 1000
        CHUNK_SIZE = 512
        chunks = [content[i:i+CHUNK_SIZE] for i in range(0, len(content), CHUNK_SIZE)]

        assert len(chunks) == 2
        assert len(chunks[0]) == 512
        assert len(chunks[1]) == 488

    def test_small_file_single_chunk(self):
        """Test that files <= 512 bytes result in single chunk"""
        content = 'x' * 512
        CHUNK_SIZE = 512
        chunks = [content[i:i+CHUNK_SIZE] for i in range(0, len(content), CHUNK_SIZE)]

        assert len(chunks) == 1
        assert len(chunks[0]) == 512

    def test_large_file_multiple_chunks(self):
        """Test that files > 512 bytes are split into multiple chunks"""
        content = 'x' * 1024
        CHUNK_SIZE = 512
        chunks = [content[i:i+CHUNK_SIZE] for i in range(0, len(content), CHUNK_SIZE)]

        assert len(chunks) == 2
        assert len(chunks[0]) == 512
        assert len(chunks[1]) == 512

    def test_chunk_file_naming(self):
        """Test chunk file naming convention"""
        path = 'http_server.py'
        chunk_prefix = f".{path}.chunk"

        assert chunk_prefix == '.http_server.py.chunk'

        chunk_files = [f"{chunk_prefix}.{i}" for i in range(3)]
        assert chunk_files == [
            '.http_server.py.chunk.0',
            '.http_server.py.chunk.1',
            '.http_server.py.chunk.2',
        ]


class TestChunkedDownload:
    """Tests for chunked file download logic"""

    def test_lambda_expression_format(self):
        """Test the lambda expression format for reading chunks"""
        path = 'test.py'
        offset = 512
        chunk_size = 512

        code = f"(lambda f:(f.seek({offset}),f.read({chunk_size}),f.close())[1])(open('{path}','r'))"

        # Verify the format is correct
        assert 'lambda f:' in code
        assert f'f.seek({offset})' in code
        assert f'f.read({chunk_size})' in code
        assert 'f.close()' in code
        assert '[1]' in code  # Return the read result (index 1 of tuple)

    def test_total_chunks_calculation(self):
        """Test total chunks calculation for non-exact size"""
        file_size = 1000
        CHUNK_SIZE = 512

        total_chunks = (file_size + CHUNK_SIZE - 1) // CHUNK_SIZE

        assert total_chunks == 2

    def test_total_chunks_exact_multiple(self):
        """Test total chunks when file size is exact multiple of chunk size"""
        file_size = 1024
        CHUNK_SIZE = 512

        total_chunks = (file_size + CHUNK_SIZE - 1) // CHUNK_SIZE

        assert total_chunks == 2

    def test_total_chunks_small_file(self):
        """Test total chunks for small file"""
        file_size = 100
        CHUNK_SIZE = 512

        total_chunks = (file_size + CHUNK_SIZE - 1) // CHUNK_SIZE

        assert total_chunks == 1


class TestReprDecoding:
    """Tests for repr string decoding used in download"""

    def test_literal_eval_decodes_simple_string(self):
        """Test that literal_eval decodes simple repr strings"""
        import ast

        repr_str = "'hello world'"
        decoded = ast.literal_eval(repr_str)

        assert decoded == 'hello world'

    def test_literal_eval_decodes_escaped_newlines(self):
        """Test that literal_eval decodes escaped newlines"""
        import ast

        repr_str = "'line1\\nline2'"
        decoded = ast.literal_eval(repr_str)

        assert decoded == 'line1\nline2'

    def test_literal_eval_decodes_escaped_quotes(self):
        """Test that literal_eval decodes escaped quotes"""
        import ast

        repr_str = "'it\\'s a test'"
        decoded = ast.literal_eval(repr_str)

        assert decoded == "it's a test"

    def test_literal_eval_decodes_unicode(self):
        """Test that literal_eval decodes unicode escape sequences"""
        import ast

        repr_str = "'hello \\u00e9'"
        decoded = ast.literal_eval(repr_str)

        assert decoded == 'hello é'

    def test_literal_eval_decodes_binary_escapes(self):
        """Test that literal_eval handles binary escape sequences"""
        import ast

        repr_str = "'\\x00\\x01\\x02'"
        decoded = ast.literal_eval(repr_str)

        assert decoded == '\x00\x01\x02'


class TestControlCharacters:
    """Tests for REPL control characters"""

    def test_ctrl_constants(self):
        """Test that control character constants are correct"""
        assert TcpRepl.CTRL_A == b'\x01'
        assert TcpRepl.CTRL_B == b'\x02'
        assert TcpRepl.CTRL_C == b'\x03'
        assert TcpRepl.CTRL_D == b'\x04'


class MockArgs:
    """Mock argparse namespace for testing commands"""
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class TestCmdExec:
    """Tests for exec command"""

    @pytest.fixture
    def mock_repl(self):
        """Create a mock TcpRepl"""
        repl = MagicMock(spec=TcpRepl)
        return repl

    def test_exec_calls_exec_and_print(self, mock_repl):
        """Test that exec calls exec_and_print with expression"""
        mock_repl.exec_and_print.return_value = True
        args = MockArgs(expr=['print("hello")'])

        result = cmd_exec(mock_repl, args)

        mock_repl.exec_and_print.assert_called_once_with('print("hello")')
        assert result is True

    def test_exec_with_empty_expr(self, mock_repl):
        """Test exec with no expression defaults to None"""
        mock_repl.exec_and_print.return_value = True
        args = MockArgs(expr=[])

        cmd_exec(mock_repl, args)

        mock_repl.exec_and_print.assert_called_once_with('None')


class TestCmdEval:
    """Tests for eval command"""

    @pytest.fixture
    def mock_repl(self):
        repl = MagicMock(spec=TcpRepl)
        return repl

    def test_eval_calls_exec_and_print(self, mock_repl):
        """Test that eval calls exec_and_print with expression"""
        mock_repl.exec_and_print.return_value = True
        args = MockArgs(expr=['1+1'])

        result = cmd_eval(mock_repl, args)

        mock_repl.exec_and_print.assert_called_once_with('1+1')
        assert result is True


class TestCmdRun:
    """Tests for run command"""

    @pytest.fixture
    def mock_repl(self):
        repl = MagicMock(spec=TcpRepl)
        return repl

    def test_run_reads_file_and_executes(self, mock_repl, tmp_path):
        """Test that run reads local file and executes it"""
        # Create a temp Python file
        script = tmp_path / "test_script.py"
        script.write_text("x = 1\nprint(x)")

        mock_repl.exec_and_print.return_value = True
        args = MockArgs(file=str(script))

        result = cmd_run(mock_repl, args)

        mock_repl.exec_and_print.assert_called_once_with("x = 1\nprint(x)")
        assert result is True

    def test_run_file_not_found(self, mock_repl):
        """Test run with non-existent file raises error"""
        args = MockArgs(file='/nonexistent/file.py')

        with pytest.raises(FileNotFoundError):
            cmd_run(mock_repl, args)


class TestCmdLs:
    """Tests for ls command"""

    @pytest.fixture
    def mock_repl(self):
        repl = MagicMock(spec=TcpRepl)
        return repl

    def test_ls_default_path(self, mock_repl):
        """Test ls with default path /"""
        mock_repl.exec_and_print.return_value = True
        args = MockArgs(path=None)

        cmd_ls(mock_repl, args)

        # Should use / as default path
        call_args = mock_repl.exec_and_print.call_args[0][0]
        assert "'/'" in call_args
        assert "__import__('os')" in call_args

    def test_ls_with_path(self, mock_repl):
        """Test ls with specific path"""
        mock_repl.exec_and_print.return_value = True
        args = MockArgs(path='/lib')

        cmd_ls(mock_repl, args)

        call_args = mock_repl.exec_and_print.call_args[0][0]
        assert "'/lib'" in call_args


class TestCmdCat:
    """Tests for cat command"""

    @pytest.fixture
    def mock_repl(self):
        repl = MagicMock(spec=TcpRepl)
        return repl

    def test_cat_strips_colon(self, mock_repl):
        """Test that cat strips leading colon from path"""
        mock_repl.exec_raw.return_value = ('100', None)  # file size
        mock_repl.exec_and_print.return_value = True
        args = MockArgs(path=':main.py')

        cmd_cat(mock_repl, args)

        # Should call open with stripped path
        call_args = mock_repl.exec_and_print.call_args[0][0]
        assert "main.py" in call_args
        assert ":main.py" not in call_args

    def test_cat_warns_large_file(self, mock_repl, capsys):
        """Test that cat warns for large files"""
        mock_repl.exec_raw.return_value = ('5000', None)  # > 4096
        mock_repl.exec_and_print.return_value = True
        args = MockArgs(path=':large.py')

        cmd_cat(mock_repl, args)

        captured = capsys.readouterr()
        assert "Warning" in captured.err
        assert "5000" in captured.err


class TestCmdCpDownload:
    """Tests for cp command - download from device"""

    @pytest.fixture
    def mock_repl(self):
        repl = MagicMock(spec=TcpRepl)
        return repl

    def test_cp_download_small_file(self, mock_repl, tmp_path, capsys):
        """Test downloading small file from device"""
        dst = tmp_path / "downloaded.py"
        mock_repl.exec_raw.side_effect = [
            ('100', None),  # file size
            ('file content here', None),  # file content
        ]
        args = MockArgs(src=':test.py', dst=str(dst))

        result = cmd_cp(mock_repl, args)

        assert result is True
        assert dst.read_text() == 'file content here'

    def test_cp_download_large_file_chunked(self, mock_repl, tmp_path, capsys):
        """Test downloading large file uses chunked transfer"""
        dst = tmp_path / "downloaded.py"
        mock_repl.exec_raw.side_effect = [
            ('600', None),  # file size > 512
            ("'chunk1'", None),  # first chunk (as repr)
            ("'chunk2'", None),  # second chunk (as repr)
        ]
        args = MockArgs(src=':big.py', dst=str(dst))

        result = cmd_cp(mock_repl, args)

        assert result is True
        assert dst.read_text() == 'chunk1chunk2'

    def test_cp_download_error(self, mock_repl, tmp_path, capsys):
        """Test download error handling"""
        dst = tmp_path / "downloaded.py"
        mock_repl.exec_raw.return_value = (None, 'file not found')
        args = MockArgs(src=':nofile.py', dst=str(dst))

        result = cmd_cp(mock_repl, args)

        assert result is False
        captured = capsys.readouterr()
        assert "Error" in captured.err


class TestCmdCpUpload:
    """Tests for cp command - upload to device"""

    @pytest.fixture
    def mock_repl(self):
        repl = MagicMock(spec=TcpRepl)
        repl.connect = MagicMock()
        repl.close = MagicMock()
        repl.enter_raw_repl = MagicMock(return_value=True)
        return repl

    def test_cp_upload_small_file(self, mock_repl, tmp_path, capsys):
        """Test uploading small file to device"""
        src = tmp_path / "local.py"
        src.write_text("print('hi')")
        mock_repl.exec_raw.return_value = (None, None)
        args = MockArgs(src=str(src), dst=':remote.py')

        result = cmd_cp(mock_repl, args)

        assert result is True
        # Check that write was called with the file content
        call_args = mock_repl.exec_raw.call_args[0][0]
        assert "remote.py" in call_args
        assert "open(" in call_args
        assert "write(" in call_args

    def test_cp_upload_large_file_chunked(self, mock_repl, tmp_path, capsys):
        """Test uploading large file uses chunked transfer"""
        src = tmp_path / "local.py"
        src.write_text("x" * 600)  # > 512 bytes

        # Mock responses for chunk writes and verifications
        mock_repl.exec_raw.side_effect = [
            (None, None),  # chunk 0 write
            ('512', None),  # chunk 0 verify
            (None, None),  # chunk 1 write
            ('88', None),   # chunk 1 verify
            (None, None),  # concat
            ('600', None),  # final verify
        ]
        args = MockArgs(src=str(src), dst=':remote.py')

        result = cmd_cp(mock_repl, args)

        assert result is True

    def test_cp_requires_colon_prefix(self, mock_repl, tmp_path, capsys):
        """Test that cp requires : prefix for device paths"""
        src = tmp_path / "local.py"
        src.write_text("x")
        args = MockArgs(src=str(src), dst='no_colon.py')

        result = cmd_cp(mock_repl, args)

        assert result is False
        captured = capsys.readouterr()
        assert "must start with ':'" in captured.err


class TestCmdRm:
    """Tests for rm command"""

    @pytest.fixture
    def mock_repl(self):
        repl = MagicMock(spec=TcpRepl)
        return repl

    def test_rm_removes_file(self, mock_repl, capsys):
        """Test rm removes file from device"""
        mock_repl.exec_raw.return_value = (None, None)
        args = MockArgs(path=':test.py')

        result = cmd_rm(mock_repl, args)

        assert result is True
        call_args = mock_repl.exec_raw.call_args[0][0]
        assert "os.remove('test.py')" in call_args

    def test_rm_strips_colon(self, mock_repl, capsys):
        """Test rm strips leading colon"""
        mock_repl.exec_raw.return_value = (None, None)
        args = MockArgs(path=':file.py')

        cmd_rm(mock_repl, args)

        call_args = mock_repl.exec_raw.call_args[0][0]
        assert "'file.py'" in call_args
        assert "':file.py'" not in call_args

    def test_rm_error(self, mock_repl, capsys):
        """Test rm error handling"""
        mock_repl.exec_raw.return_value = (None, 'OSError: file not found')
        args = MockArgs(path='nofile.py')

        result = cmd_rm(mock_repl, args)

        assert result is False
        captured = capsys.readouterr()
        assert "Error" in captured.err


class TestCmdMkdir:
    """Tests for mkdir command"""

    @pytest.fixture
    def mock_repl(self):
        repl = MagicMock(spec=TcpRepl)
        return repl

    def test_mkdir_creates_directory(self, mock_repl, capsys):
        """Test mkdir creates directory on device"""
        mock_repl.exec_raw.return_value = (None, None)
        args = MockArgs(path=':newdir')

        result = cmd_mkdir(mock_repl, args)

        assert result is True
        call_args = mock_repl.exec_raw.call_args[0][0]
        assert "os.mkdir('newdir')" in call_args

    def test_mkdir_strips_colon(self, mock_repl, capsys):
        """Test mkdir strips leading colon"""
        mock_repl.exec_raw.return_value = (None, None)
        args = MockArgs(path=':mydir')

        cmd_mkdir(mock_repl, args)

        call_args = mock_repl.exec_raw.call_args[0][0]
        assert "'mydir'" in call_args

    def test_mkdir_error(self, mock_repl, capsys):
        """Test mkdir error handling"""
        mock_repl.exec_raw.return_value = (None, 'OSError: directory exists')
        args = MockArgs(path='existing')

        result = cmd_mkdir(mock_repl, args)

        assert result is False
        captured = capsys.readouterr()
        assert "Error" in captured.err


class TestCmdReset:
    """Tests for reset command"""

    @pytest.fixture
    def mock_repl(self):
        repl = MagicMock(spec=TcpRepl)
        return repl

    def test_reset_sends_reset_command(self, mock_repl, capsys):
        """Test reset sends machine.reset()"""
        mock_repl.exec_raw.return_value = (None, None)
        args = MockArgs()

        result = cmd_reset(mock_repl, args)

        assert result is True
        call_args = mock_repl.exec_raw.call_args[0][0]
        assert "reset()" in call_args
        assert "machine" in call_args

        captured = capsys.readouterr()
        assert "resetting" in captured.out


class TestExecAndPrint:
    """Tests for exec_and_print method"""

    @pytest.fixture
    def repl_with_mock_socket(self):
        """Create a TcpRepl with mocked socket"""
        repl = TcpRepl('192.168.1.1', 80)
        repl.sock = MagicMock()
        repl.in_raw_mode = True
        return repl

    def test_exec_and_print_decodes_repr_string(self, repl_with_mock_socket, capsys):
        """Test that repr strings are decoded"""
        repl = repl_with_mock_socket
        repl.sock.recv.side_effect = [b"OK\x04'hello world'\x04\x04>"]

        result = repl.exec_and_print("'hello world'")

        captured = capsys.readouterr()
        assert captured.out.strip() == 'hello world'
        assert result is True

    def test_exec_and_print_raw_mode(self, repl_with_mock_socket, capsys):
        """Test raw mode preserves repr strings"""
        repl = repl_with_mock_socket
        repl.sock.recv.side_effect = [b"OK\x04'hello'\x04\x04>"]

        result = repl.exec_and_print("'hello'", raw=True)

        captured = capsys.readouterr()
        assert captured.out.strip() == "'hello'"

    def test_exec_and_print_error(self, repl_with_mock_socket, capsys):
        """Test error output goes to stderr"""
        repl = repl_with_mock_socket
        repl.sock.recv.side_effect = [b"OK\x04\x04NameError: x\x04>"]

        result = repl.exec_and_print("x")

        captured = capsys.readouterr()
        assert "NameError" in captured.err
        assert result is False


class TestCmdSync:
    """Tests for sync command"""

    @pytest.fixture
    def mock_repl(self):
        repl = MagicMock(spec=TcpRepl)
        return repl

    def test_sync_fetches_remote_files(self, mock_repl, tmp_path, capsys, monkeypatch):
        """Test that sync fetches remote file list"""
        # Create local files
        (tmp_path / "main.py").write_text("print('hello')")

        # Mock remote file list response
        mock_repl.exec_raw.return_value = ('{"main.py": 100}', None)

        monkeypatch.setattr('builtins.input', lambda _: 'n')

        args = MockArgs(directory=str(tmp_path), force=False, reboot=False)
        cmd_sync(mock_repl, args)

        # Should have called exec_raw to get file list
        assert mock_repl.exec_raw.called
        call_args = mock_repl.exec_raw.call_args_list[0][0][0]
        assert "listdir" in call_args

    def test_sync_detects_modified_files(self, mock_repl, tmp_path, capsys, monkeypatch):
        """Test that sync detects files with different sizes"""
        # Create local file with different size than remote
        (tmp_path / "main.py").write_text("x" * 200)

        # Mock remote with different size
        mock_repl.exec_raw.return_value = ('{"main.py": 100}', None)

        # Mock input to cancel
        monkeypatch.setattr('builtins.input', lambda _: 'n')

        args = MockArgs(directory=str(tmp_path), force=False, reboot=False)
        cmd_sync(mock_repl, args)

        captured = capsys.readouterr()
        assert "modified" in captured.out
        assert "main.py" in captured.out

    def test_sync_detects_new_files(self, mock_repl, tmp_path, capsys, monkeypatch):
        """Test that sync detects new files not on device"""
        # Create local file
        (tmp_path / "main.py").write_text("content")

        # Mock empty remote
        mock_repl.exec_raw.return_value = ('{}', None)

        monkeypatch.setattr('builtins.input', lambda _: 'n')

        args = MockArgs(directory=str(tmp_path), force=False, reboot=False)
        cmd_sync(mock_repl, args)

        captured = capsys.readouterr()
        assert "new" in captured.out

    def test_sync_force_updates_all(self, mock_repl, tmp_path, capsys, monkeypatch):
        """Test that --force updates all files regardless of size"""
        # Create local file with same size as remote
        (tmp_path / "main.py").write_text("x" * 100)

        # Mock remote with same size
        mock_repl.exec_raw.return_value = ('{"main.py": 100}', None)

        monkeypatch.setattr('builtins.input', lambda _: 'n')

        args = MockArgs(directory=str(tmp_path), force=True, reboot=False)
        cmd_sync(mock_repl, args)

        captured = capsys.readouterr()
        assert "forced" in captured.out

    def test_sync_all_up_to_date(self, mock_repl, tmp_path, capsys):
        """Test sync when all files are up to date"""
        # Create local file with same size as remote
        (tmp_path / "main.py").write_text("x" * 100)

        # Mock remote with same size
        mock_repl.exec_raw.return_value = ('{"main.py": 100}', None)

        args = MockArgs(directory=str(tmp_path), force=False, reboot=False)
        result = cmd_sync(mock_repl, args)

        assert result is True
        captured = capsys.readouterr()
        assert "up to date" in captured.out

    def test_sync_handles_error(self, mock_repl, tmp_path, capsys):
        """Test sync handles remote errors"""
        mock_repl.exec_raw.return_value = (None, "Connection error")

        args = MockArgs(directory=str(tmp_path), force=False, reboot=False)
        result = cmd_sync(mock_repl, args)

        assert result is False
        captured = capsys.readouterr()
        assert "Error" in captured.err
