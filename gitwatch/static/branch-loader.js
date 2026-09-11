'use strict';

// Keep a late GitHub response from replacing choices for a different repository.
class GitWatchBranchLoader {
  constructor(fetcher, onChange) {
    this.fetcher = fetcher;
    this.onChange = onChange;
    this.sequence = 0;
    this.reset();
  }
  reset(url = '') {
    this.sequence += 1;
    this.state = {url, branches:[], defaultBranch:'', loading:false, loaded:false, error:''};
    this.onChange?.(this.state);
  }
  async load(url) {
    const sequence = ++this.sequence;
    this.state = {url, branches:[], defaultBranch:'', loading:true, loaded:false, error:''};
    this.onChange?.(this.state);
    try {
      const data = await this.fetcher(url);
      if (sequence !== this.sequence) return;
      if (!Array.isArray(data.branches) || !data.branches.every(branch => typeof branch === 'string')) {
        throw new Error('Не удалось прочитать список веток. Обнови список.');
      }
      this.state = {url, branches:data.branches, defaultBranch:data.default_branch || '', loading:false, loaded:true, error:''};
    } catch (error) {
      if (sequence !== this.sequence) return;
      this.state = {url, branches:[], defaultBranch:'', loading:false, loaded:false, error:error.message || 'Не удалось загрузить ветки.'};
    }
    this.onChange?.(this.state);
  }
}
if (typeof module !== 'undefined' && module.exports) module.exports = GitWatchBranchLoader;
