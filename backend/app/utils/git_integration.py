"""
Git integration utilities for repository operations
"""
import asyncio
import aiohttp
import json
import base64
from typing import Dict, List, Any, Optional, Tuple
import logging
from urllib.parse import urlparse
import os
import time

logger = logging.getLogger(__name__)

class GitIntegration:
    """Integration with Git services (GitHub, GitLab, etc.)"""

    def __init__(self):
        self.github_api_base = "https://api.github.com"
        self.gitlab_api_base = "https://gitlab.com/api/v4"
        self.session = None
        # Load GitHub token from environment
        self.github_token = os.getenv("GITHUB_ACCESS_TOKEN")
        if self.github_token:
            masked_token = self.github_token[:8] + "..." + self.github_token[-4:] if len(self.github_token) > 12 else "***"
            logger.info(f"✅ GitHub token loaded: {masked_token} (5000 requests/hour)")
        else:
            logger.warning("⚠️ No GitHub token found. Rate limits: 60 requests/hour")

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session

    async def close(self):
        """Close HTTP session"""
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None
            logger.info("✅ HTTP session closed")

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def get_repository_metadata(self, repo_url: str, access_token: str = None) -> Optional[Dict[str, Any]]:
        """
        Get repository metadata from Git service

        Args:
            repo_url: Repository URL
            access_token: Optional access token

        Returns:
            Repository metadata
        """
        try:
            parsed_url = urlparse(repo_url)
            hostname = parsed_url.netloc

            if 'github.com' in hostname:
                return await self._get_github_repo_metadata(repo_url, access_token or self.github_token)
            elif 'gitlab.com' in hostname:
                return await self._get_gitlab_repo_metadata(repo_url, access_token)
            else:
                logger.warning(f"Unsupported Git host: {hostname}")
                return None

        except Exception as e:
            logger.error(f"Failed to get repository metadata: {str(e)}")
            return None
        finally:
            # Don't close session here - let it be reused
            pass

    async def _get_github_repo_metadata(self, repo_url: str, access_token: str = None) -> Optional[Dict[str, Any]]:
        """Get GitHub repository metadata"""
        try:
            path_parts = urlparse(repo_url).path.strip('/').split('/')
            if len(path_parts) < 2:
                logger.error(f"Invalid GitHub URL: {repo_url}")
                return None

            owner, repo = path_parts[0], path_parts[1]

            headers = {
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "AI-Code-Review-Assistant"
            }

            if access_token:
                headers["Authorization"] = f"token {access_token}"
                logger.info(f"Using authenticated GitHub API for {owner}/{repo}")
            else:
                logger.warning(f"Using unauthenticated GitHub API for {owner}/{repo} (60 requests/hour)")

            session = await self._get_session()
            api_url = f"{self.github_api_base}/repos/{owner}/{repo}"
            logger.info(f"Fetching GitHub repo metadata: {api_url}")

            async with session.get(api_url, headers=headers) as response:
                logger.info(f"GitHub API response status: {response.status}")
                
                # Handle rate limit errors
                if response.status == 403:
                    error_text = await response.text()
                    if "rate limit" in error_text.lower():
                        logger.error("🚫 GitHub API rate limit exceeded. Add a token to increase limits.")
                        return None
                    elif "not found" in error_text.lower():
                        logger.error(f"❌ Repository {owner}/{repo} not found")
                        return None
                
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"✅ Successfully fetched metadata for {owner}/{repo}")
                    return {
                        "id": data.get("id"),
                        "name": data.get("name"),
                        "full_name": data.get("full_name"),
                        "description": data.get("description"),
                        "url": data.get("html_url"),
                        "clone_url": data.get("clone_url"),
                        "default_branch": data.get("default_branch"),
                        "language": data.get("language"),
                        "stars": data.get("stargazers_count"),
                        "forks": data.get("forks_count"),
                        "open_issues": data.get("open_issues_count"),
                        "private": data.get("private"),
                        "created_at": data.get("created_at"),
                        "updated_at": data.get("updated_at"),
                        "owner": {
                            "login": data.get("owner", {}).get("login"),
                            "avatar_url": data.get("owner", {}).get("avatar_url")
                        },
                        "topics": data.get("topics", []),
                        "license": data.get("license", {}).get("name") if data.get("license") else None,
                        "supports_webhooks": True
                    }
                elif response.status == 404:
                    logger.error(f"❌ Repository {owner}/{repo} not found")
                    return None
                else:
                    error_text = await response.text()
                    logger.error(f"GitHub API error: {response.status} - {error_text}")
                    return None

        except Exception as e:
            logger.error(f"Failed to get GitHub metadata: {str(e)}", exc_info=True)
            return None

    async def _get_gitlab_repo_metadata(self, repo_url: str, access_token: str = None) -> Optional[Dict[str, Any]]:
        """Get GitLab repository metadata"""
        try:
            path = urlparse(repo_url).path.strip('/')

            headers = {
                "Accept": "application/json"
            }

            if access_token:
                headers["Private-Token"] = access_token

            session = await self._get_session()
            encoded_path = path.replace('/', '%2F')
            api_url = f"{self.gitlab_api_base}/projects/{encoded_path}"
            logger.info(f"Fetching GitLab repo metadata: {api_url}")

            async with session.get(api_url, headers=headers) as response:
                logger.info(f"GitLab API response status: {response.status}")
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"Successfully fetched metadata for {path}")
                    return {
                        "id": data.get("id"),
                        "name": data.get("name"),
                        "description": data.get("description"),
                        "url": data.get("web_url"),
                        "clone_url": data.get("http_url_to_repo"),
                        "default_branch": data.get("default_branch"),
                        "language": self._detect_gitlab_language(data.get("statistics", {})),
                        "stars": data.get("star_count", 0),
                        "forks": data.get("forks_count", 0),
                        "open_issues": data.get("open_issues_count", 0),
                        "private": not data.get("public", True),
                        "created_at": data.get("created_at"),
                        "updated_at": data.get("last_activity_at"),
                        "owner": {
                            "username": data.get("namespace", {}).get("name"),
                            "avatar_url": data.get("namespace", {}).get("avatar_url")
                        },
                        "topics": data.get("tag_list", []),
                        "license": data.get("license", {}).get("name") if data.get("license") else None,
                        "supports_webhooks": True
                    }
                else:
                    error_text = await response.text()
                    logger.error(f"GitLab API error: {response.status} - {error_text}")
                    return None

        except Exception as e:
            logger.error(f"Failed to get GitLab metadata: {str(e)}", exc_info=True)
            return None

    def _detect_gitlab_language(self, statistics: Dict[str, Any]) -> Optional[str]:
        """Detect primary language from GitLab statistics"""
        if not statistics:
            return None

        languages = statistics.get("languages", {})
        if languages:
            return max(languages.items(), key=lambda x: x[1])[0]

        return None

    async def get_files(self, repo_url: str, path: str = "/", recursive: bool = False,
                        ref: str = None, access_token: str = None) -> List[Dict[str, Any]]:
        """
        List files and directories in a repository path

        Args:
            repo_url: Repository URL
            path: Path within repository (default root)
            recursive: Whether to list recursively (not always supported)
            ref: Branch/tag/commit reference (defaults to repo's default branch)
            access_token: Optional access token

        Returns:
            List of file/directory entries with metadata
        """
        try:
            parsed_url = urlparse(repo_url)
            hostname = parsed_url.netloc

            if 'github.com' in hostname:
                return await self._get_github_files(repo_url, path, recursive, ref, access_token or self.github_token)
            elif 'gitlab.com' in hostname:
                return await self._get_gitlab_files(repo_url, path, recursive, ref, access_token)
            else:
                logger.warning(f"Unsupported Git host: {hostname}")
                return []

        except Exception as e:
            logger.error(f"Failed to get files: {str(e)}", exc_info=True)
            return []

    async def _get_github_files(self, repo_url: str, path: str, recursive: bool,
                                ref: str = None, access_token: str = None) -> List[Dict[str, Any]]:
        """List files from GitHub using Contents API"""
        try:
            path_parts = urlparse(repo_url).path.strip('/').split('/')
            if len(path_parts) < 2:
                logger.error(f"Invalid GitHub URL: {repo_url}")
                return []

            owner, repo = path_parts[0], path_parts[1]

            headers = {
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "AI-Code-Review-Assistant"
            }

            # Use token if available
            if access_token:
                headers["Authorization"] = f"token {access_token}"
                logger.info(f"Using authenticated GitHub API for {owner}/{repo}")
            else:
                logger.warning(f"Using unauthenticated GitHub API for {owner}/{repo} (60 requests/hour)")

            session = await self._get_session()
            api_path = path.lstrip('/')
            
            # GitHub API expects empty string for root
            if api_path == '' or api_path == '/':
                api_url = f"{self.github_api_base}/repos/{owner}/{repo}/contents/"
            else:
                api_url = f"{self.github_api_base}/repos/{owner}/{repo}/contents/{api_path}"
            
            if ref:
                api_url += f"?ref={ref}"
                
            logger.info(f"Fetching GitHub files: {api_url}")

            async with session.get(api_url, headers=headers) as response:
                logger.info(f"GitHub API response status: {response.status}")
                
                # Handle rate limit errors
                if response.status == 403:
                    error_text = await response.text()
                    if "rate limit" in error_text.lower():
                        logger.error("🚫 GitHub API rate limit exceeded. Add a token to increase limits.")
                        return []
                    elif "not found" in error_text.lower():
                        logger.error(f"❌ Path not found: {path}")
                        return []
                
                if response.status == 200:
                    data = await response.json()
                    files = []
                    for item in data:
                        files.append({
                            "id": item.get("sha"),
                            "name": item.get("name"),
                            "path": item.get("path"),
                            "type": "folder" if item.get("type") == "dir" else "file",
                            "size": item.get("size", 0),
                            "modified": item.get("last_modified") or item.get("updated_at"),
                            "language": self._guess_language(item.get("name")),
                            "download_url": item.get("download_url")
                        })
                    logger.info(f"✅ Found {len(files)} items in {path}")
                    return files
                elif response.status == 404:
                    logger.warning(f"Path not found: {path}")
                    return []
                else:
                    error_text = await response.text()
                    logger.error(f"GitHub API error: {response.status} - {error_text}")
                    return []

        except Exception as e:
            logger.error(f"Failed to get GitHub files: {str(e)}", exc_info=True)
            return []

    async def _get_gitlab_files(self, repo_url: str, path: str, recursive: bool,
                                ref: str = None, access_token: str = None) -> List[Dict[str, Any]]:
        """List files from GitLab using Repository Tree API"""
        try:
            project_path = urlparse(repo_url).path.strip('/')

            headers = {
                "Accept": "application/json"
            }

            if access_token:
                headers["Private-Token"] = access_token

            session = await self._get_session()
            encoded_path = project_path.replace('/', '%2F')
            api_url = f"{self.gitlab_api_base}/projects/{encoded_path}/repository/tree"
            params = {
                "path": path.lstrip('/'),
                "recursive": recursive,
                "per_page": 100
            }
            if ref:
                params["ref"] = ref
            logger.info(f"Fetching GitLab files: {api_url} with params {params}")

            async with session.get(api_url, headers=headers, params=params) as response:
                logger.info(f"GitLab API response status: {response.status}")
                if response.status == 200:
                    data = await response.json()
                    files = []
                    for item in data:
                        files.append({
                            "id": item.get("id"),
                            "name": item.get("name"),
                            "path": item.get("path"),
                            "type": "folder" if item.get("type") == "tree" else "file",
                            "size": item.get("size", 0),
                            "modified": None,  # GitLab tree doesn't include modification time
                            "language": self._guess_language(item.get("name")),
                            "download_url": None
                        })
                    logger.info(f"Found {len(files)} items in {path}")
                    return files
                else:
                    error_text = await response.text()
                    logger.error(f"GitLab API error: {response.status} - {error_text}")
                    return []

        except Exception as e:
            logger.error(f"Failed to get GitLab files: {str(e)}", exc_info=True)
            return []

    def _guess_language(self, filename: str) -> str:
        """Guess language from file extension"""
        ext_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.jsx': 'javascript',
            '.tsx': 'typescript',
            '.java': 'java',
            '.c': 'c',
            '.cpp': 'cpp',
            '.h': 'c',
            '.hpp': 'cpp',
            '.cs': 'csharp',
            '.go': 'go',
            '.rb': 'ruby',
            '.php': 'php',
            '.html': 'html',
            '.css': 'css',
            '.json': 'json',
            '.yml': 'yaml',
            '.yaml': 'yaml',
            '.md': 'markdown',
            '.rst': 'rst',
            '.txt': 'text',
        }
        for ext, lang in ext_map.items():
            if filename.endswith(ext):
                return lang
        return 'unknown'

    async def get_file_content(self, repo_url: str, file_path: str, ref: str = "main",
                              access_token: str = None) -> Optional[str]:
        """
        Get file content from repository

        Args:
            repo_url: Repository URL
            file_path: Path to file
            ref: Branch/tag/commit reference
            access_token: Optional access token

        Returns:
            File content as string
        """
        try:
            parsed_url = urlparse(repo_url)
            hostname = parsed_url.netloc

            if 'github.com' in hostname:
                return await self._get_github_file_content(repo_url, file_path, ref, access_token or self.github_token)
            elif 'gitlab.com' in hostname:
                return await self._get_gitlab_file_content(repo_url, file_path, ref, access_token)
            else:
                logger.warning(f"Unsupported Git host: {hostname}")
                return None

        except Exception as e:
            logger.error(f"Failed to get file content: {str(e)}")
            return None

    async def _get_github_file_content(self, repo_url: str, file_path: str, ref: str,
                                      access_token: str = None) -> Optional[str]:
        """Get file content from GitHub"""
        try:
            path_parts = urlparse(repo_url).path.strip('/').split('/')
            if len(path_parts) < 2:
                return None

            owner, repo = path_parts[0], path_parts[1]

            headers = {
                "Accept": "application/vnd.github.v3.raw",
                "User-Agent": "AI-Code-Review-Assistant"
            }

            if access_token:
                headers["Authorization"] = f"token {access_token}"
                logger.info("Using authenticated GitHub API (5000 requests/hour)")

            session = await self._get_session()
            api_url = f"{self.github_api_base}/repos/{owner}/{repo}/contents/{file_path}?ref={ref}"
            logger.info(f"Fetching GitHub file content: {api_url}")

            async with session.get(api_url, headers=headers) as response:
                logger.info(f"GitHub API response status: {response.status}")
                
                # Handle rate limit errors
                if response.status == 403:
                    error_text = await response.text()
                    if "rate limit" in error_text.lower():
                        logger.error("🚫 GitHub API rate limit exceeded. Add a token to increase limits.")
                        return None
                
                if response.status == 200:
                    # Try to get as raw content first
                    content_type = response.headers.get('content-type', '')
                    if 'application/json' in content_type:
                        # If we got JSON, it might be a directory or file metadata
                        data = await response.json()
                        if isinstance(data, list):
                            logger.warning(f"Path {file_path} is a directory, not a file")
                            return None
                        if data.get("encoding") == "base64":
                            content = base64.b64decode(data.get("content", "")).decode('utf-8')
                            return content
                    else:
                        # Raw content
                        return await response.text()
                elif response.status == 404:
                    logger.warning(f"File not found: {file_path}")
                    return None
                else:
                    error_text = await response.text()
                    logger.error(f"GitHub API error: {response.status} - {error_text}")
                    return None

        except Exception as e:
            logger.error(f"Failed to get GitHub file content: {str(e)}", exc_info=True)
            return None

    async def _get_gitlab_file_content(self, repo_url: str, file_path: str, ref: str,
                                      access_token: str = None) -> Optional[str]:
        """Get file content from GitLab"""
        try:
            path = urlparse(repo_url).path.strip('/')

            headers = {
                "Accept": "application/json"
            }

            if access_token:
                headers["Private-Token"] = access_token

            session = await self._get_session()
            encoded_path = path.replace('/', '%2F')
            encoded_file_path = file_path.replace('/', '%2F')
            api_url = f"{self.gitlab_api_base}/projects/{encoded_path}/repository/files/{encoded_file_path}/raw?ref={ref}"
            logger.info(f"Fetching GitLab file content: {api_url}")

            async with session.get(api_url, headers=headers) as response:
                logger.info(f"GitLab API response status: {response.status}")
                if response.status == 200:
                    return await response.text()
                else:
                    error_text = await response.text()
                    logger.error(f"GitLab API error: {response.status} - {error_text}")
                    return None

        except Exception as e:
            logger.error(f"Failed to get GitLab file content: {str(e)}", exc_info=True)
            return None

    async def get_recent_commits(self, repo_url: str, branch: str = "main",
                                limit: int = 10, access_token: str = None) -> List[Dict[str, Any]]:
        """
        Get recent commits from repository

        Args:
            repo_url: Repository URL
            branch: Branch name
            limit: Number of commits to fetch
            access_token: Optional access token

        Returns:
            List of recent commits
        """
        try:
            parsed_url = urlparse(repo_url)
            hostname = parsed_url.netloc

            if 'github.com' in hostname:
                return await self._get_github_commits(repo_url, branch, limit, access_token or self.github_token)
            elif 'gitlab.com' in hostname:
                return await self._get_gitlab_commits(repo_url, branch, limit, access_token)
            else:
                logger.warning(f"Unsupported Git host: {hostname}")
                return []

        except Exception as e:
            logger.error(f"Failed to get recent commits: {str(e)}", exc_info=True)
            return []

    async def _get_github_commits(self, repo_url: str, branch: str, limit: int,
                                 access_token: str = None) -> List[Dict[str, Any]]:
        """Get recent commits from GitHub"""
        try:
            path_parts = urlparse(repo_url).path.strip('/').split('/')
            if len(path_parts) < 2:
                return []

            owner, repo = path_parts[0], path_parts[1]

            headers = {
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "AI-Code-Review-Assistant"
            }

            if access_token:
                headers["Authorization"] = f"token {access_token}"
                logger.info(f"Using authenticated GitHub API for {owner}/{repo}")

            session = await self._get_session()
            api_url = f"{self.github_api_base}/repos/{owner}/{repo}/commits?sha={branch}&per_page={limit}"
            logger.info(f"Fetching GitHub commits: {api_url}")

            async with session.get(api_url, headers=headers) as response:
                logger.info(f"GitHub API response status: {response.status}")
                
                # Handle rate limit errors
                if response.status == 403:
                    error_text = await response.text()
                    if "rate limit" in error_text.lower():
                        logger.error("🚫 GitHub API rate limit exceeded. Add a token to increase limits.")
                        return []
                    elif "not found" in error_text.lower():
                        logger.error(f"❌ Repository {owner}/{repo} not found")
                        return []
                
                if response.status == 200:
                    commits_data = await response.json()
                    commits = []
                    for commit_data in commits_data:
                        commit = commit_data.get("commit", {})
                        author = commit.get("author", {})
                        commits.append({
                            "sha": commit_data.get("sha", "")[:8],
                            "message": commit.get("message", "").split('\n')[0],  # First line only
                            "full_message": commit.get("message", ""),
                            "author": {
                                "name": author.get("name", ""),
                                "email": author.get("email", "")
                            },
                            "date": author.get("date", ""),
                            "url": commit_data.get("html_url", "")
                        })
                    logger.info(f"✅ Found {len(commits)} commits")
                    return commits
                elif response.status == 404:
                    logger.error(f"❌ Repository {owner}/{repo} not found")
                    return []
                else:
                    error_text = await response.text()
                    logger.error(f"GitHub API error: {response.status} - {error_text}")
                    return []

        except Exception as e:
            logger.error(f"Failed to get GitHub commits: {str(e)}", exc_info=True)
            return []

    async def _get_gitlab_commits(self, repo_url: str, branch: str, limit: int,
                                 access_token: str = None) -> List[Dict[str, Any]]:
        """Get recent commits from GitLab"""
        try:
            path = urlparse(repo_url).path.strip('/')

            headers = {
                "Accept": "application/json"
            }

            if access_token:
                headers["Private-Token"] = access_token

            session = await self._get_session()
            encoded_path = path.replace('/', '%2F')
            api_url = f"{self.gitlab_api_base}/projects/{encoded_path}/repository/commits?ref_name={branch}&per_page={limit}"
            logger.info(f"Fetching GitLab commits: {api_url}")

            async with session.get(api_url, headers=headers) as response:
                logger.info(f"GitLab API response status: {response.status}")
                if response.status == 200:
                    commits_data = await response.json()
                    commits = []
                    for commit_data in commits_data:
                        commits.append({
                            "sha": commit_data.get("id", "")[:8],
                            "message": commit_data.get("message", "").split('\n')[0],
                            "full_message": commit_data.get("message", ""),
                            "author": {
                                "name": commit_data.get("author_name", ""),
                                "email": commit_data.get("author_email", "")
                            },
                            "date": commit_data.get("created_at", ""),
                            "url": commit_data.get("web_url", "")
                        })
                    logger.info(f"Found {len(commits)} commits")
                    return commits
                else:
                    error_text = await response.text()
                    logger.error(f"GitLab API error: {response.status} - {error_text}")
                    return []

        except Exception as e:
            logger.error(f"Failed to get GitLab commits: {str(e)}", exc_info=True)
            return []

    async def get_pull_requests(self, repo_url: str, state: str = "open",
                               limit: int = 10, access_token: str = None,
                               page: int = 1) -> List[Dict[str, Any]]:
        """
        Get pull requests/merge requests from repository

        Args:
            repo_url: Repository URL
            state: State of PRs (open, closed, all)
            limit: Number of PRs to fetch
            access_token: Optional access token
            page: Page number for pagination

        Returns:
            List of pull requests
        """
        try:
            parsed_url = urlparse(repo_url)
            hostname = parsed_url.netloc

            if 'github.com' in hostname:
                return await self._get_github_pull_requests(repo_url, state, limit, access_token or self.github_token, page)
            elif 'gitlab.com' in hostname:
                return await self._get_gitlab_merge_requests(repo_url, state, limit, access_token, page)
            else:
                logger.warning(f"Unsupported Git host: {hostname}")
                return []

        except Exception as e:
            logger.error(f"Failed to get pull requests: {str(e)}", exc_info=True)
            return []

    async def _get_github_pull_requests(self, repo_url: str, state: str, limit: int,
                                       access_token: str = None, page: int = 1) -> List[Dict[str, Any]]:
        """Get GitHub pull requests"""
        try:
            path_parts = urlparse(repo_url).path.strip('/').split('/')
            if len(path_parts) < 2:
                return []

            owner, repo = path_parts[0], path_parts[1]

            headers = {
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "AI-Code-Review-Assistant"
            }

            if access_token:
                headers["Authorization"] = f"token {access_token}"
                logger.info(f"Using authenticated GitHub API for {owner}/{repo}")

            session = await self._get_session()
            api_url = f"{self.github_api_base}/repos/{owner}/{repo}/pulls?state={state}&per_page={limit}&page={page}"
            logger.info(f"Fetching GitHub pull requests: {api_url}")

            async with session.get(api_url, headers=headers) as response:
                logger.info(f"GitHub API response status: {response.status}")
                
                # Handle rate limit errors
                if response.status == 403:
                    error_text = await response.text()
                    if "rate limit" in error_text.lower():
                        logger.error("🚫 GitHub API rate limit exceeded. Add a token to increase limits.")
                        return []
                
                if response.status == 200:
                    prs_data = await response.json()
                    prs = []
                    for pr_data in prs_data:
                        prs.append({
                            "id": pr_data.get("id"),
                            "number": pr_data.get("number"),
                            "title": pr_data.get("title"),
                            "state": pr_data.get("state"),
                            "user": pr_data.get("user", {}).get("login"),
                            "created_at": pr_data.get("created_at"),
                            "updated_at": pr_data.get("updated_at"),
                            "url": pr_data.get("html_url"),
                            "diff_url": pr_data.get("diff_url"),
                            "head": {
                                "ref": pr_data.get("head", {}).get("ref"),
                                "sha": pr_data.get("head", {}).get("sha")
                            },
                            "base": {
                                "ref": pr_data.get("base", {}).get("ref"),
                                "sha": pr_data.get("base", {}).get("sha")
                            }
                        })
                    logger.info(f"✅ Found {len(prs)} pull requests")
                    return prs
                else:
                    error_text = await response.text()
                    logger.error(f"GitHub API error: {response.status} - {error_text}")
                    return []

        except Exception as e:
            logger.error(f"Failed to get GitHub pull requests: {str(e)}", exc_info=True)
            return []

    async def _get_gitlab_merge_requests(self, repo_url: str, state: str, limit: int,
                                        access_token: str = None, page: int = 1) -> List[Dict[str, Any]]:
        """Get GitLab merge requests"""
        try:
            path = urlparse(repo_url).path.strip('/')

            headers = {
                "Accept": "application/json"
            }

            if access_token:
                headers["Private-Token"] = access_token

            session = await self._get_session()
            encoded_path = path.replace('/', '%2F')
            api_url = f"{self.gitlab_api_base}/projects/{encoded_path}/merge_requests?state={state}&per_page={limit}&page={page}"
            logger.info(f"Fetching GitLab merge requests: {api_url}")

            async with session.get(api_url, headers=headers) as response:
                logger.info(f"GitLab API response status: {response.status}")
                if response.status == 200:
                    mrs_data = await response.json()
                    mrs = []
                    for mr_data in mrs_data:
                        mrs.append({
                            "id": mr_data.get("id"),
                            "iid": mr_data.get("iid"),
                            "title": mr_data.get("title"),
                            "state": mr_data.get("state"),
                            "author": mr_data.get("author", {}).get("username"),
                            "created_at": mr_data.get("created_at"),
                            "updated_at": mr_data.get("updated_at"),
                            "url": mr_data.get("web_url"),
                            "source_branch": mr_data.get("source_branch"),
                            "target_branch": mr_data.get("target_branch"),
                            "sha": mr_data.get("sha")
                        })
                    logger.info(f"Found {len(mrs)} merge requests")
                    return mrs
                else:
                    error_text = await response.text()
                    logger.error(f"GitLab API error: {response.status} - {error_text}")
                    return []

        except Exception as e:
            logger.error(f"Failed to get GitLab merge requests: {str(e)}", exc_info=True)
            return []

    async def create_webhook(self, repo_url: str, user_id: int,
                            webhook_url: str = None, access_token: str = None) -> Optional[str]:
        """
        Create a webhook for the repository

        Args:
            repo_url: Repository URL
            user_id: User ID for webhook configuration
            webhook_url: Webhook URL (defaults to app's webhook endpoint)
            access_token: Optional access token

        Returns:
            Webhook ID if successful, None otherwise
        """
        try:
            parsed_url = urlparse(repo_url)
            hostname = parsed_url.netloc

            if 'github.com' in hostname:
                return await self._create_github_webhook(repo_url, user_id, webhook_url, access_token or self.github_token)
            elif 'gitlab.com' in hostname:
                return await self._create_gitlab_webhook(repo_url, user_id, webhook_url, access_token)
            else:
                logger.warning(f"Unsupported Git host: {hostname}")
                return None

        except Exception as e:
            logger.error(f"Failed to create webhook: {str(e)}", exc_info=True)
            return None

    async def _create_github_webhook(self, repo_url: str, user_id: int,
                                    webhook_url: str = None, access_token: str = None) -> Optional[str]:
        """Create GitHub webhook"""
        try:
            path_parts = urlparse(repo_url).path.strip('/').split('/')
            if len(path_parts) < 2:
                return None

            owner, repo = path_parts[0], path_parts[1]

            if not webhook_url:
                base_url = os.getenv("APP_BASE_URL", "http://localhost:8000")
                webhook_url = f"{base_url}/api/webhooks/github"

            headers = {
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "AI-Code-Review-Assistant"
            }

            if access_token:
                headers["Authorization"] = f"token {access_token}"

            webhook_data = {
                "name": "web",
                "active": True,
                "events": ["push", "pull_request"],
                "config": {
                    "url": webhook_url,
                    "content_type": "json",
                    "secret": os.getenv("GITHUB_WEBHOOK_SECRET", "your-webhook-secret")
                }
            }

            session = await self._get_session()
            api_url = f"{self.github_api_base}/repos/{owner}/{repo}/hooks"
            logger.info(f"Creating GitHub webhook: {api_url}")

            async with session.post(api_url, headers=headers, json=webhook_data) as response:
                logger.info(f"GitHub API response status: {response.status}")
                if response.status in [200, 201]:
                    data = await response.json()
                    return str(data.get("id"))
                else:
                    error_text = await response.text()
                    logger.error(f"GitHub API error: {response.status} - {error_text}")
                    return None

        except Exception as e:
            logger.error(f"Failed to create GitHub webhook: {str(e)}", exc_info=True)
            return None

    async def _create_gitlab_webhook(self, repo_url: str, user_id: int,
                                    webhook_url: str = None, access_token: str = None) -> Optional[str]:
        """Create GitLab webhook"""
        try:
            path = urlparse(repo_url).path.strip('/')

            if not webhook_url:
                base_url = os.getenv("APP_BASE_URL", "http://localhost:8000")
                webhook_url = f"{base_url}/api/webhooks/gitlab"

            headers = {
                "Accept": "application/json"
            }

            if access_token:
                headers["Private-Token"] = access_token

            webhook_data = {
                "url": webhook_url,
                "push_events": True,
                "merge_requests_events": True,
                "enable_ssl_verification": True,
                "token": os.getenv("GITLAB_WEBHOOK_SECRET", "your-webhook-secret")
            }

            session = await self._get_session()
            encoded_path = path.replace('/', '%2F')
            api_url = f"{self.gitlab_api_base}/projects/{encoded_path}/hooks"
            logger.info(f"Creating GitLab webhook: {api_url}")

            async with session.post(api_url, headers=headers, json=webhook_data) as response:
                logger.info(f"GitLab API response status: {response.status}")
                if response.status == 201:
                    data = await response.json()
                    return str(data.get("id"))
                else:
                    error_text = await response.text()
                    logger.error(f"GitLab API error: {response.status} - {error_text}")
                    return None

        except Exception as e:
            logger.error(f"Failed to create GitLab webhook: {str(e)}", exc_info=True)
            return None

    async def delete_webhook(self, repo_url: str, webhook_id: str,
                            access_token: str = None) -> bool:
        """
        Delete a webhook from repository

        Args:
            repo_url: Repository URL
            webhook_id: Webhook ID to delete
            access_token: Optional access token

        Returns:
            True if successful, False otherwise
        """
        try:
            parsed_url = urlparse(repo_url)
            hostname = parsed_url.netloc

            if 'github.com' in hostname:
                return await self._delete_github_webhook(repo_url, webhook_id, access_token or self.github_token)
            elif 'gitlab.com' in hostname:
                return await self._delete_gitlab_webhook(repo_url, webhook_id, access_token)
            else:
                logger.warning(f"Unsupported Git host: {hostname}")
                return False

        except Exception as e:
            logger.error(f"Failed to delete webhook: {str(e)}", exc_info=True)
            return False

    async def _delete_github_webhook(self, repo_url: str, webhook_id: str,
                                    access_token: str = None) -> bool:
        """Delete GitHub webhook"""
        try:
            path_parts = urlparse(repo_url).path.strip('/').split('/')
            if len(path_parts) < 2:
                return False

            owner, repo = path_parts[0], path_parts[1]

            headers = {
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "AI-Code-Review-Assistant"
            }

            if access_token:
                headers["Authorization"] = f"token {access_token}"

            session = await self._get_session()
            api_url = f"{self.github_api_base}/repos/{owner}/{repo}/hooks/{webhook_id}"
            logger.info(f"Deleting GitHub webhook: {api_url}")

            async with session.delete(api_url, headers=headers) as response:
                logger.info(f"GitHub API response status: {response.status}")
                return response.status == 204

        except Exception as e:
            logger.error(f"Failed to delete GitHub webhook: {str(e)}", exc_info=True)
            return False

    async def _delete_gitlab_webhook(self, repo_url: str, webhook_id: str,
                                    access_token: str = None) -> bool:
        """Delete GitLab webhook"""
        try:
            path = urlparse(repo_url).path.strip('/')

            headers = {
                "Accept": "application/json"
            }

            if access_token:
                headers["Private-Token"] = access_token

            session = await self._get_session()
            encoded_path = path.replace('/', '%2F')
            api_url = f"{self.gitlab_api_base}/projects/{encoded_path}/hooks/{webhook_id}"
            logger.info(f"Deleting GitLab webhook: {api_url}")

            async with session.delete(api_url, headers=headers) as response:
                logger.info(f"GitLab API response status: {response.status}")
                return response.status == 204

        except Exception as e:
            logger.error(f"Failed to delete GitLab webhook: {str(e)}", exc_info=True)
            return False