"""
Test the update page handler
"""
import pytest


class TestUpdatePage:
    @pytest.mark.asyncio
    async def test_update_page_returns_html(self, client):
        """Test that /update returns an HTML page."""
        response = await client.get("/update")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "Update Adapter" in response.text
        assert "Upload New Version" in response.text

    @pytest.mark.asyncio
    async def test_update_page_has_file_input(self, client):
        """Test that the update page has a file input."""
        response = await client.get("/update")
        assert 'type="file"' in response.text
        assert 'id="exeFile"' in response.text
        assert 'accept=".exe"' in response.text

    @pytest.mark.asyncio
    async def test_update_page_has_back_link(self, client):
        """Test that the update page has a link back to health page."""
        response = await client.get("/update")
        assert 'href="/"' in response.text
        assert "Back to Health" in response.text

    @pytest.mark.asyncio
    async def test_update_page_has_rollback_button(self, client):
        """Test that the update page has rollback functionality."""
        response = await client.get("/update")
        assert "Rollback" in response.text
        assert "rollbackBtn" in response.text

    @pytest.mark.asyncio
    async def test_update_page_has_backup_list(self, client):
        """Test that the update page displays backup list."""
        response = await client.get("/update")
        assert "Available backups" in response.text
        assert "backupList" in response.text

    @pytest.mark.asyncio
    async def test_update_page_shows_current_version(self, client):
        """Test that the update page shows the current version."""
        response = await client.get("/update")
        from version import VERSION
        assert f"v{VERSION}" in response.text



