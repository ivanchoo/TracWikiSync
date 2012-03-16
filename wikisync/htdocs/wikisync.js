(function() {
	var MODEL_KEYS = [
		'name', 
		'ignore', 
		'ignore_attachment', 
        'sync_time', 
        'sync_remote_version', 
        'sync_local_version',
        'remote_version', 
        'local_version', 
        'status'
    ];
    
    var TREE_NODE_TEMPLATE = 
		'<li id="<%- cid %>" class="<%- status %>">' +
		'  <p class="controls">' +
		'    <a href="<%- remoteUrl %>" class="ext-link" target="_blank"><i class="icon">&nbsp;</i>Remote</a>' +
		'    <i>or</i>' +
		'    <a href="#" class="ignore">Ignore</a>' +
		'    <a href="#" class="unignore">Unignore</a>' +
		'  </p>' +
		'  <p>' +
		'    <i class="status"><%- status.toUpperCase() %></i>' +
		'	 <a  style="margin-left:<%= level * 10 %>px" href="<%- localUrl %>"><%= name %></a>' +
		'  </p>' +
		'  <% if (error) { %>' +
		'    <p class="indent error"><strong>Error:</strong> <%- error %></p>' +
		'  <% } else if (status == "conflict") { %>' +
		'    <p class="indent">' +
        '      <label for="<%- cid %>-skip" class="<%= resolve == "skip" ? "selected" : "" %>">' +
        '        <input type="radio" value="skip" id="<%- cid %>-skip" class="resolve" name="<%- cid %>" <%= resolve == "skip" ? checked="checked" : "" %> />' +
        '        Decide later' +
        '      </label>' +
        '      <label for="<%- cid %>-modified" class="<%= resolve == "modified" ? "selected" : "" %>">' +
        '        <input type="radio" value="modified" id="<%- cid %>-modified" class="resolve" name="<%- cid %>" <%= resolve == "modified" ? checked="checked" : "" %> />' +
        '        Update to <%- remoteServer %>' +
        '      </label>' +
        '      <label for="<%- cid %>-outdated" class="<%= resolve == "outdated" ? "selected" : "" %>">' +
        '        <input type="radio" value="outdated" id="<%- cid %>-outdated" class="resolve" name="<%- cid %>" <%= resolve == "outdated" ? checked="checked" : "" %> />' +
        '        Copy from <%- remoteServer %>' +
        '      </label>' +
        '    </p>' +
		'  <% } %>' + 
		'</li>';

	var TREE_NESTED_NODE_TEMPLATE = 
		'<li>' +
		'  <p class="controls">' +
		'    <a href="#" class="ignore-all">Ignore All</a>' +
		'    <i>or</i>' +
		'    <a href="#" class="unignore-all">Unignore All</a>' +
		'  </p>' +
		'  <p class="indent"><strong style="margin-left:<%= level * 10 %>px"><%= name %></strong></p>' +
		'  <ul><%= nested %></ul>' +
		'</li>';

	var PROGRESS_PANEL_TEMPLATE = 
		'<div id="wikisync-modal" class="wikisync-modal">' +
		'	<div class="wikisync-modal-overlay">&nbsp;</div>' +
		'	<div class="wikisync-modal-panel">' +
		'		<h2>Synchronization in progress..</h2>' +
		'		<p>Do not close this window during synchronization.</p>' +
		'		<textarea></textarea>' +
		'		<p style="text-align:right"><input type="button" value="Stop Synchronization" /></p>' +
		'	</div>' +
		'</div>';
		
	var SPLIT_NUMBER_REGEX = new RegExp('([0-9.]+)', 'g');
	var SPLIT_REGEX = new RegExp('(/| |_)', 'g');
	var SPLIT_CAMELCASE_REGEX = new RegExp('([a-z])([A-Z])(?=[a-z])');
	
	/*
	 * Splits the model name by camelcase, numbers, forward slash
	 * and underscore, and returns an array of the following structure:
	 * [
	 *   ['tokenized keyword n n', model],
	 *   [ ... ],
	 *   ...,
	 * ]
	 */
	var tokenizeModelByName = function(models) {
		return _.reduce(models, function(memo, model) {
			memo.push([
				model.get('name')
					.replace(SPLIT_CAMELCASE_REGEX, '$1 $2')
					.replace(SPLIT_NUMBER_REGEX, ' $1')
					.replace(SPLIT_REGEX, ' ').split(' '),
				model
			]);
			return memo;
		}, []);
	}
	
	/* Groups the tokenized structure by the first keyword in the tokens:
	 * {
	 *   'keyword': [ [tokenizeModelByName], [tokenizeModelByName], ..],
	 *   'keyword2': [ ..],
	 *   ...,
	 * }
	 */
	var groupByFirstTokenKeyword = function(entries, key, nodes) {
		var grouped = _.groupBy(entries, function(entry) {
			/* entry = [[key1, key2, ..], model] */
			return entry[0] ? entry[0].shift() : '';
		});
		var subKeys = [];
		var subEntries = [];
		for(var k in grouped) {
			subKeys.push(k);
			subEntries.push(grouped[k]);
		}
		return {
			subKeys: subKeys,
			subEntries: subEntries,
			nodes: nodes,
			key: key
		}
	};
	
	/* Formats an array of models into the following nested structure:
	 * [ model,
	 *   model,
	 *   [ 'groupedNamePrefix', [ model, model, ..] ],
	 *   model,
	 *   ...
	 * ]
	 */
	var groupByModelNameHierachy = function(models) {
		var minSize = 2,
			results = [],
			stack = [groupByFirstTokenKeyword(tokenizeModelByName(models), '', results)],
			state, key, subEntries, subNodes, parent, name, subKey;
		while(true) {
			/* Using recursive callbacks results in Maximum stack call exceeded error
			 * in browsers when handling large number of models. Had to resort to 
			 * manually managing a stack to work avoid using recursive callbacks.
			 */
			state = stack[0];
			if (!state.subKeys.length) {
				parent = stack[1];
				if (parent) {
					stack.shift();
				} else {
					break;
				}
			}
			key = state.subKeys.shift();
			subEntries = state.subEntries.shift();
			nodes = state.nodes;
			if (key && subEntries.length > minSize) {
				name = subEntries[0][1].get('name').substr(state.key.length);
				subKey = state.key + name.substr(0, name.indexOf(key) + key.length);
				subNodes = [];
				nodes.push([subKey, subNodes]);
				stack.unshift(groupByFirstTokenKeyword(subEntries, subKey, subNodes));
			} else {
				_.each(subEntries, function(entry) {
					nodes.push(entry[1]);
				});
			}
		}
		return results;
	};
	
	var strEndsWith = function(str, ends) {
		return str.length >= ends.length && str.substring(str.length - ends.length) === ends;
	};
	
	var formatUrl = function(base) {
		if (!strEndsWith(base, '/')) {
			base += '/';
		}
		return base + encodeURI(_.rest(arguments).join('/'));
	};
	
	var isRegExp = function(str) {
		return _.detect('^$.()[]|'.split(''), function(c) {
			return str.indexOf(c) >= 0;
		}) != undefined;
	}
	
   	var pad = function(n) {
   		return n < 10 ? '0' + n : n;
   	}
    
    var formatDate = function(dte) {
    	if (_.isUndefined(dte)) {
    		dte = new Date();
    	}
		return dte.getFullYear() + '-'
			+ pad(dte.getMonth() + 1) + '-'
			+ pad(dte.getDate()) + ' '
			+ pad(dte.getHours()) + ':'
			+ pad(dte.getMinutes()) + ':'
			+ pad(dte.getSeconds());
    }
    
    /* Represents a wiki synchronization state */
	var WikiSyncModel = Backbone.Model.extend({
		defaults: {
			resolve: 'skip',
			status: 'unknown',
			error: null
		},
		initialize: function() {

		},
		parse: function(data) {
			/* Note: must follow the field order as defined in wikisync.model */
			return _.reduce(data, function(memo, value, index) {
				memo[MODEL_KEYS[index]] = value;
				return memo;
			}, {});
		}
	});
	
	/* Repesents a collection of WikiSyncModel */
	var WikiSyncCollection = Backbone.Collection.extend({
		model: WikiSyncModel,
		formToken: null,
		initialize: function(models, opts) {
			this.url = opts.url;
		},
		comparator: function(model) {
			/* Always sort by name */
			return model.get('name');
		},
		sync: function(model, resolveAs) {
			if (!_.isString(resolveAs)) {
				resolveAs = model.get('status');
			}
			var action;
			switch(resolveAs) {
				case 'new':
				case 'modified':
					action = 'push';
					break;
				case 'missing':
				case 'outdated':
					action = 'pull';
					break;
				default:
					action = 'refresh';
			}
			var data = [
				{ name:'name', value:model.get('name') },
				{ name:'action', value:action }
			];
			this._post({ 
				data:data,
				beforeSend: function() {
					model.trigger('progress', model);
				},
				complete: function(xhr, status) {
					if (status == 'error') {
						model.set({ error:xhr.responseText });
					}
					model.trigger('complete', model, status, action);
				}
			});
		},
		ignore: function(models, isIgnore) {
			if (!models || !models.length) return;
			var self = this;
			var data = _.map(models, function(model) {
				return { name:'name', value:model.get('name') };
			});
			data.push({ name:'action', value:'resolve' });
			data.push({ name:'status', value:isIgnore ? 'ignore' : 'unignore' });
			this._post({ 
				data:data,
				beforeSend: function() {
					_.each(models, function(model) {
						model.trigger('progress', model);
					});
				},
				complete: function(xhr, status) {
					_.each(models, function(model) {
						if (status == 'error') {
							model.set({ error:xhr.responseText });
						}
						model.trigger('complete', model, status, isIgnore ? 'ignore' : 'unignore');
					});
				}
			});
		},
		_post: function(opts) {
			if (_.isArray(opts.data)) {
				/* Must include form token injected by trac,
				 * else form post won't get processed.
				 */
				opts.data.push({ name:'__FORM_TOKEN', value:this.formToken });
			}
			var self = this;
			var map = this.reduce(function(memo, model) {
				memo[model.get('name')] = model;
				return memo;
			}, {});
			$.ajax(
				$.extend({
					url: this.url,
					type: 'POST',
					dataType: 'json',
					success: function(data, status, xhr) {
						_.each(data, function(item) {
							var name = item[0];
							var model = map[name];
							if (model) {
								model.unset('error', { silent:true });
								model.set(model.parse(item));
							} else {
								self.add([data], { parse:true });
							}
						});
					}
				}, opts)
			);
			
		}
	});
	
	
	/* Wikisync pulldown panel as seen at the navigation context menu */
	var WikiSyncPageView = Backbone.View.extend({
		el: 'body',
		events: {
			'click #wikisync-panel-toggle': 'onPanelToggle',
			'click #wikisync-panel-close': 'onPanelToggle'
		},
		initialize: function() {
			_.bindAll(this);
		},
		render: function() {
			var $panel = this.$('#wikisync-panel').hide();
			var $radios = $panel.find('input[type="radio"]');
			if ($radios.length) {
				/* for conflict status */
				$radios.bind('change', this.onRadioChange);
				$panel.find('input[type="submit"]').attr('disabled', 'disabled');
			}
			return this;
		},
		toggle: function() {
			var $panel = this.$('#wikisync-panel');
			if ($panel.is(':visible')) {
				$panel.hide();
			} else {
				var $link = this.$('#wikisync-panel-toggle');
				var pos = $link.offset();
				$panel.stop()
					.css({
						top: pos.top + $link.outerHeight() + 4,
						right: $(window).width() - pos.left - $link.outerWidth() - 6
					})
					.fadeIn();
			}
		},
		onPanelToggle: function(evt) {
			evt.preventDefault();
			this.toggle();
		},
		onRadioChange: function(evt) {
			this.$('#wikisync-panel')
				.find('input[type="submit"]')
				.removeAttr('disabled');
		}
	});
	
	/* Main wikisync view */
	var WikiSyncView = Backbone.View.extend({
		events: {
			'click #wikisync-form input[type="submit"]': 'onSync',
			'click #wikisync-modal input[type="button"]': 'onProgressClick',
			'change #wikisync-form input.filter': 'onFilter',
			'change #filter-conflict-resolve': 'onGlobalResolve',
			'keydown #filter-text': 'onFilterTextChange',
			'click #filter-text-reset': 'onFilterTextReset',
			'change #wikisync-list input.resolve': 'onResolve',
			'mouseover #wikisync-list': 'onListOver',
			'mouseout #wikisync-list': 'onListOut',
			'click .ignore,.ignore-all': 'onIgnore',
			'click .unignore,.unignore-all': 'onIgnore'
		},
		initialize: function(opts) {
			_.bindAll(this);
			this.localUrl = opts['localUrl'] || '';
			this.remoteUrl = opts['remoteUrl'] || '';
			this.nodeTemplate = _.template(TREE_NODE_TEMPLATE);
			this.nestedNodeTemplate = _.template(TREE_NESTED_NODE_TEMPLATE);
			this.$form = this.$('#wikisync-form');
			this.$list = this.$('#wikisync-list');
			this.$empty = this.$('#wikisync-empty');
			this.collection.formToken = this.$form.find('input[name~=__FORM_TOKEN]').val();
			this.collection.bind('all', this.onCollectionEvent);
		},
		render: function() {
			this.renderTree();
			return this;
		},
		renderTree: function(force, includeModels) {
			if (force) {
				this.filterHash = '__refresh__';
			}
			var filterKeys = { 'unknown':true },
				filterKeyword = this.$('#filter-text').val(),
				filterModels = {},
				filterRegExp, $input, name;
			if (filterKeyword) {
				if (isRegExp(filterKeyword)) {
					try {
						filterRegExp = new RegExp(filterKeyword);
					} catch(err) {
						/* ignore */
					}
				}
				filterKeyword = filterKeyword.toUpperCase();
			}
			this.$('input.filter').each(function() {
				$input = $(this);
				if ($input.is(':checked')) {
					filterKeys[$input.val()] = true;
				}
			});
			if (_.isArray(includeModels)) {
				_.each(includeModels, function(model) {
					filterModels[model.cid] = true;
				});
			}
			var filtered = this.collection.filter(function(model) {
				if (filterModels[model.cid]) {
					return true;
				}
				if (filterKeys[model.get('status')]) {
					if (filterKeyword) {
						name = model.get('name');
						if (filterRegExp) {
							return filterRegExp.exec(name);
						}
						return name.toUpperCase().indexOf(filterKeyword) >= 0; 
					}
					return true;
				}
				return false;
			});
			var filterHash = filterKeyword + _.map(filtered, function(model) {
				return model.cid;
			}).join('');
			if (filterHash != this.filterHash) {
				/* avoid expensive redraw by comparing filterHash */
				var tree = groupByModelNameHierachy(filtered);
				var hint = '<i class="hint">Displaying ' + filtered.length + ' of ' + this.collection.length + ' pages</i>';
				if (tree.length) {
					tree = [['Everything ' + hint, tree]];
					var content = _.map(tree, function(child) {
						return this.formatTreeNode(child, 0);
					}, this)
					this.$list.empty().html(content.join('')).show();
					this.$empty.hide();
				} else {
					this.$list.hide().empty();
					this.$empty.show();
				}
				this.filterHash = filterHash;
			}
			return this;
		},
		formatTreeNode: function(node, level) {
			level = level || 0;
			if (_.isArray(node)) {
				var data = {
					cid: _.uniqueId("group"),
					name: node[0],
					level: level,
					nested: _.map(node[1], function(child) {
						return this.formatTreeNode(child, level + 1)
					}, this).join('')
				};
				return this.nestedNodeTemplate(data);
			} else {
				var data = node.toJSON();
				var name = node.get('name');
				var data = $.extend({
					cid: node.cid,
					level: level,
					localUrl: formatUrl(this.localUrl, name),
					remoteUrl: formatUrl(this.remoteUrl, 'wiki', name),
					error: null,
					resolve: 'skip',
					remoteServer: this.options.remoteServer
				}, node.toJSON());
				return this.nodeTemplate(data);
			}
		},
		sync: function(bool) {
			if (_.isUndefined(bool)) {
				bool = !_.isArray(this.syncPending);
			}
			if (bool == _.isArray(this.syncPending)) {
				return this;
			}
			if (!bool) {
				this.syncPending = null;
			} else {
				var collection = this.collection,
					pending = [],
					resolveConflict = this.resolveConflict,
					$el, model;
				this.$list.find('li').each(function() {
					$el = $(this);
					if ($el.is('.grouped,.ignored,.synced')) {
						return true;
					}
					model = collection.getByCid($el.attr('id'));
					if (!model || (model.get('status') == 'conflict' && resolveConflict(model) == 'skip')) {
						return true;
					}
					pending.push(model);
				});
				if (!pending.length) {
					alert('Nothing to synchronize! Please edit your filter options.');
				} else {
					this.syncPending = pending;
					this.syncNext();
				}
			}
			return this;
		},
		syncNext: function() {
			var model = this.syncPending ? this.syncPending.shift() : null;
			if (!model) {
				this.syncPending = null;
				return false;
			} else {
				var resolveAs;
				if (model.get('status') == 'conflict') {
					resolveAs = $('#filter-conflict-resolve').val() || model.get('resolve');
					if (resolveAs == 'skip') {
						this.syncNext();
						return this;
					}
				}
				this.collection.sync(model, resolveAs);
				return model;
			}
		},
		resolveConflict: function(model) {
			if (model.get('status') == 'conflict') {
				return $('#filter-conflict-resolve').val() || model.get('resolve');
			}
			return 'skip';
		},
		updateResolveInput: function(model, value, disabled) {
			var $input,
				$inputs = this.$('#' + model.cid + ' input.resolve');
			if ($inputs.is(':disabled') != disabled) {
				if (disabled) {
					$inputs.attr('disabled', 'disabled');
				} else {
					$inputs.removeAttr('disabled');
				}
			}
			$inputs.each(function() {
				$input = $(this);
				if ($input.attr('value') == value) {
					$input.parent().addClass('selected');
					$input.attr('checked', 'checked');
				} else {
					$input.parent().removeClass('selected');
					$input.removeAttr('checked');
				}
			});
			return this;
		},
		updateChangedModels: function() {
			if (!this.changedModels) return this;
			if (this.changedModels.length > 30) {
				/* cheaper to just redraw everything */
				this.renderTree(true, this.changedModels);
			} else {
				var model, $el, $new;
				_.each(this.changedModels, function(model) {
					var $el = this.$('#' + model.cid);
					if ($el.length) {
						var $new = $(this.formatTreeNode(model)).hide();
						$el.replaceWith($new);
						$new.fadeIn();
					}
				}, this);
			}
			this.changedModels = null;
			return this;
		},
		progressHandler: function(state, model, action) {
			if (!this.syncPending) return;
			var complete = false,
				message, alertMessage;
			if (!this.$progress) {
				this.$progress = $(PROGRESS_PANEL_TEMPLATE).appendTo(this.$el);
				this.errorCount = 0;
				this.$el.css({ overflow:'hidden' });
			}
			if (state == 'error') {
				this.errorCount++;
				message = 'ERROR: ' + model.get('name') + ' cannot be sync due to the following reason:\n' +
					'    "' + model.get('error') + '".';
				if (this.errorCount > 5) {
					alertMessage = 'Synchronization is interrupted as too many error has occurred.';
					this.sync(false);
					complete = true;
				}
			} else if (state == 'success') {
				message = model.get('name');
				switch(action) {
					case 'push':
						message += ' is updated to ' + this.options.remoteServer + '.';
						break;
					case 'pull':
						message += ' is copied from ' + this.options.remoteServer + '.';
						break
					case 'refresh':
						message += ' current status is now "' + model.get('status').toUpperCase() + '".';
						break;
					default:
						message += ' is successfully synced.';
				}
			} else if (state == 'interrupt') {
				complete = true;
				this.sync(false);
				message = 'Interrupted';
			} else {
				return this;
			}
			
			if (!complete && !this.syncNext()) {
				alertMessage = 'Synchronization complete.';
				this.sync(false);
				complete = true;
			}
			if (complete) {
				this.$progress.find('input[type="button"]').val('Close');
			}
			if (alertMessage) {
				_.defer(function() {
					alert(alertMessage);
				});
			}
			if (message) {
				message = '[' + formatDate() + '] ' + message;
				if (alertMessage) {
					message += '\n[' + formatDate() + '] ' + alertMessage;
				}
				var $textarea = this.$progress.find('textarea');
				$textarea.val($textarea.val() + message + '\n');
				$textarea.attr('scrollTop', $textarea.attr('scrollHeight'));
			}
			return this;
		},
		onCollectionEvent: function(type, model, status, action) {
			if (type == 'change') {
				if (!this.changedModels) {
					this.changedModels = [model];
					_.defer(this.updateChangedModels);
				} else {
					this.changedModels.push(model);
				}
				return;
			}
			if (type == 'progress') {
				var $el = model && model.cid ? this.$('#' + model.cid) : null;
				$el.addClass('progress');
				this.progressHandler('progress', model, action);
			} else if (type == 'complete') {
				if (status != 'success') {
					this.progressHandler('error', model, action);
				} else {
					this.progressHandler('success', model, action);
				}
			}
		},
		onSync: function(evt) {
			evt.preventDefault();
			this.sync(!this.syncPending);
		},
		onFilter: function(evt) {
			var $el = $(evt.target);
			if ($el.is(':checked')) {
				$el.parent().addClass('selected');
			} else {
				$el.parent().removeClass('selected');
			}
			this.renderTree();
		},
		onFilterTextChange: function(evt) {
			if (!this.filterLater) {
				var self = this;
				this.filterLater = _.debounce(function() {
					if (self.filterPending) {
						self.filterPending = false;
						self.renderTree();
					}
				}, 1000);
			}
			if (evt.keyCode == 13) {
				evt.preventDefault();
				this.filterPending = false;
				this.renderTree();
			} else {
				this.filterPending = true;
				this.filterLater();
			}
		},
		onFilterTextReset: function(evt) {
			evt.preventDefault();
			this.$('#filter-text').val('');
			this.filterPending = false;
			this.renderTree();
		},
		onListOver: function(evt) {
			var $el = $(evt.target);
			if (!$el.is('li')) {
				$el = $el.parent();
			}
			if ($el.is('li')) {
				if (this.$hover) {
					this.$hover.removeClass('hover');
				}
				this.$hover = $el.addClass('hover');
			}
		},
		onListOut: _.debounce(function(evt) {
			if (!this.$hover) return;
			/* Easiest way is to check if mouse is within the list boundary
			 * and remove the hover state accordingly */
			var pos = this.$list.offset(),
				x = evt.pageX,
				y = evt.pageY;
			if (x < pos.left ||
				y < pos.top ||
				x > pos.left + this.$list.outerWidth() ||
				y > pos.top + this.$list.outerHeight()) {
				this.$hover.removeClass('hover');
				this.$hover = null;
			}
		}, 500),
		onGlobalResolve: function(evt) {
			var val = $(evt.target).val(),
				conflicts = this.collection.filter(function(model) {
					return model.get('status') == 'conflict';
				});
			if (val) {
				_.each(conflicts, function(model) {
					this.updateResolveInput(model, val, true);
				}, this);
			} else {
				_.each(conflicts, function(model) {
					val = model.get('resolve') || 'skip';
					this.updateResolveInput(model, val, false);
				}, this);
			}
		},
		onResolve: function(evt) {
			var $input = $(evt.target);
			var id = $input.attr('name');
			var val = $input.val();
			var model = this.collection.getByCid(id);
			if (model) {
				model.set({ resolve:val }, { silent:true });
			}
			this.updateResolveInput(model, val, false);
		},
		onIgnore: function(evt) {
			evt.preventDefault();
			var $target = $(evt.target);
			var isIgnore = true;
			var $li = $target.parents('li:first');
			if ($target.hasClass('ignore-all')) {
				$li = $li.find('li');
			} else if ($target.hasClass('unignore-all')) {
				$li = $li.find('li');
				isIgnore = false
			} else if ($target.hasClass('unignore')) {
				isIgnore = false;
			}
			var clz = isIgnore ? 'ignored' : 'unignored';
			var models = [], 
				collection = this.collection,
				model;
			$li.each(function() {
				var $el = $(this);
				if ($el.hasClass('group')) {
					return;
				} else if (isIgnore && $el.hasClass('ignored')) {
					return;
				} else if (!isIgnore && !$el.hasClass('ignored')) {
					return;
				}
				model = collection.getByCid($el.attr('id'));
				if (model) {
					models.push(model);
				}
			});
			var num = models ? models.length : 0;
			var verb = isIgnore ? 'ignored' : 'unignored';
			if (num) {
				if (num > 30) {
					if (!confirm('Do you want to ' + verb + ' ' + num + ' pages?')) {
						return;
					}
				}
				this.collection.ignore(models, isIgnore);
			} else {
				alert('All pages are already ' + verb);
			}
		},
		onProgressClick: function(evt) {
			if (this.syncPending) {
				this.progressHandler('interrupt');
			} else {
				if (this.$progress) {
					this.$progress.remove();
					this.$progress = null;
				}
				this.$el.css({ overflow:'auto' });
			}
		}
		
	});
	
	
	var root = this;
	root.wikisync = {
		WikiSyncModel: WikiSyncModel,
		WikiSyncCollection: WikiSyncCollection,
		WikiSyncView: WikiSyncView,
		WikiSyncPageView: WikiSyncPageView
	};
	
}());