#
# Apache v2 license
# Copyright (C) 2024 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

import queue
import time
import pytest
from threading import Event, Semaphore
from unittest.mock import MagicMock, patch, call
from src.server.gstreamer_app_source import GStreamerAppSource, GvaFrameData
from src.server.gstreamer_pipeline import GStreamerPipeline


@pytest.fixture
def mock_pipeline():
    pipeline = MagicMock(spec=GStreamerPipeline)
    pipeline.appsrc_element = MagicMock()
    return pipeline


@pytest.fixture
def input_queue():
    return queue.Queue()


def _make_source(mock_pipeline, input_queue, mode='pull'):
    request = {
        'source': {
            'input': input_queue,
            'mode': mode,
        }
    }
    src = GStreamerAppSource.__new__(GStreamerAppSource)
    src._src = mock_pipeline.appsrc_element
    src._input_queue = input_queue
    src._stop = False
    src._push_frames = Event()
    src._pull_semaphore = Semaphore(0)
    src._mode = GStreamerAppSource.Mode(mode)
    return src


class TestGStreamerAppSourcePullMode:
    """Tests for PULL mode with worker thread (non-blocking mainloop)."""

    def test_start_frames_releases_pull_semaphore(self, mock_pipeline, input_queue):
        src = _make_source(mock_pipeline, input_queue, mode='pull')
        # The semaphore starts at 0; start_frames should release it
        assert src._pull_semaphore._value == 0
        src.start_frames()
        assert src._pull_semaphore._value == 1

    def test_pause_frames_noop_in_pull_mode(self, mock_pipeline, input_queue):
        src = _make_source(mock_pipeline, input_queue, mode='pull')
        # pause_frames should be a no-op in pull mode (no exception raised)
        src.pause_frames()

    def test_finish_unblocks_pull_worker(self, mock_pipeline, input_queue):
        src = _make_source(mock_pipeline, input_queue, mode='pull')
        # finish() should release the semaphore to unblock any waiting thread
        src.finish()
        assert src._stop is True
        # semaphore should have been released
        assert src._pull_semaphore._value == 1


class TestGStreamerAppSourcePushMode:
    """Tests for PUSH mode with Event-based continuous pushing."""

    def test_start_frames_sets_event(self, mock_pipeline, input_queue):
        src = _make_source(mock_pipeline, input_queue, mode='push')
        src.start_frames()
        assert src._push_frames.is_set()

    def test_pause_frames_clears_event(self, mock_pipeline, input_queue):
        src = _make_source(mock_pipeline, input_queue, mode='push')
        src._push_frames.set()
        src.pause_frames()
        assert not src._push_frames.is_set()

    def test_finish_sets_stop_and_unblocks_thread(self, mock_pipeline, input_queue):
        src = _make_source(mock_pipeline, input_queue, mode='push')
        src.finish()
        assert src._stop is True
        assert src._push_frames.is_set()


class TestGStreamerAppSourceBufferCreation:
    """Tests for buffer allocation optimizations."""

    def test_create_input_frame_uses_new_wrapped(self, mock_pipeline, input_queue, mocker):
        src = _make_source(mock_pipeline, input_queue, mode='pull')
        mock_buffer = MagicMock()
        mock_new_wrapped = mocker.patch(
            'src.server.gstreamer_app_source.Gst.Buffer.new_wrapped',
            return_value=mock_buffer,
        )
        data = b'\x00\x01\x02\x03'
        item = GvaFrameData(data=data)
        mocker.patch(
            'src.server.gstreamer_app_source.Gst.Sample.new',
            return_value=MagicMock(),
        )
        src._create_input_frame(item)
        mock_new_wrapped.assert_called_once_with(data)

    def test_create_input_frame_no_new_allocate(self, mock_pipeline, input_queue, mocker):
        src = _make_source(mock_pipeline, input_queue, mode='pull')
        mock_new_alloc = mocker.patch(
            'src.server.gstreamer_app_source.Gst.Buffer.new_allocate',
        )
        mocker.patch(
            'src.server.gstreamer_app_source.Gst.Buffer.new_wrapped',
            return_value=MagicMock(),
        )
        mocker.patch(
            'src.server.gstreamer_app_source.Gst.Sample.new',
            return_value=MagicMock(),
        )
        data = b'\x00\x01\x02\x03'
        item = GvaFrameData(data=data)
        src._create_input_frame(item)
        mock_new_alloc.assert_not_called()

    def test_create_input_frame_non_bytes_raises(self, mock_pipeline, input_queue):
        src = _make_source(mock_pipeline, input_queue, mode='pull')
        item = GvaFrameData(data="not bytes")
        with pytest.raises(Exception, match="GvaFrameData must contain bytes"):
            src._create_input_frame(item)

    def test_create_input_frame_gst_sample_passthrough(self, mock_pipeline, input_queue, mocker):
        from gi.repository import Gst
        src = _make_source(mock_pipeline, input_queue, mode='pull')
        mock_sample = MagicMock(spec=Gst.Sample)
        result = src._create_input_frame(mock_sample)
        assert result is mock_sample

    def test_create_input_frame_gva_sample_returns_inner_sample(
            self, mock_pipeline, input_queue, mocker):
        from src.server.gstreamer_app_destination import GvaSample
        src = _make_source(mock_pipeline, input_queue, mode='pull')
        inner_sample = MagicMock()
        gva_sample = GvaSample(inner_sample)
        result = src._create_input_frame(gva_sample)
        assert result is inner_sample
