(function() {
	var MODEL_KEYS = [
		"name", "ignore", "ignore_attachment", 
        "sync_time", "sync_remote_version", "sync_local_version",
        "remote_version", "local_version"
    ];

	var SPLIT_NUMBER_REGEX = new RegExp('([0-9.]+)', 'g');
	var SPLIT_REGEX = new RegExp('(/| |_)', 'g');
	var SPLIT_CAMELCASE_REGEX = new RegExp('([a-z])([A-Z])(?=[a-z])');
	
	var TREE_NODE_TEMPLATE = 
		'<li id="<%- cid %>" class="<%- status %>">' + 
		'  <div class="item-wrapper">' +
		'    <a href="<%- localUrl %>" target="_blank"><%= name %></a>' + 
		'    <% if (status == "conflict") { %>' +
		'      <span class="resolve-wrapper">' +
		'        <i>Resolve as:</i>' +
        '        <label for="<%- cid %>-skip">' +
        '          <input type="radio" value="skip" id="<%- cid %>-skip" class="resolve" name="<%- cid %>" checked="checked" /> Skip' +
        '        </label>' +
        '        <label for="<%- cid %>-modified" class="modified">' +
        '          <input type="radio" value="modified" id="<%- cid %>-modified" class="resolve" name="<%- cid %>" /> Modified' +
        '        </label>' +
        '        <label for="<%- cid %>-outdated" class="outdated">' +
        '          <input type="radio" value="outdated" id="<%- cid %>-outdated" class="resolve" name="<%- cid %>" /> Outdated' +
        '        </label>' +
        '      </span>' +
		'    <% } %>' + 
		'    <div class="controls">' + 
		'      <a href="<%- remoteUrl %>" target="_blank">❏ View Remote</a>' + 
		'      <i>or</i>' + 
		'      <a href="#" class="ignore-item">✘ Ignore</a>' + 
		'      <a href="#" class="unignore-item">✔ Unignore</a>' + 
		'    </div>' + 
		'  </div>' +
		'</li>';
	
	var TREE_NESTED_NODE_TEMPLATE = 
		'<li id="<%- cid %>" class="grouped">' + 
		'  <div class="item-wrapper">' + 
		'    <strong><%= name %></strong>' + 
		'    <span class="controls">  ' + 
		'      <a href="#" class="unignore-all">✔✔ Unignore All</a>' + 
		'      <i> or </i>' + 
		'      <a href="#" class="ignore-all">✘✘ Ignore All</a>' + 
		'    </span>' + 
		'  </div>' +
		'  <ul class="nested"><%= nested %></ul>' +
		'</li>';
	
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
	
	var groupByTokenState = function(entries, key, nodes) {
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
	
	var groupByTokenHierachy = function(models) {
		var minSize = 2,
			results = [],
			stack = [groupByTokenState(tokenizeModelByName(models), '', results)],
			state, key, subEntries, subNodes, parent, name, subKey;
		while(true) {
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
				stack.unshift(groupByTokenState(subEntries, subKey, subNodes));
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
    
	var WikiSyncModel = Backbone.Model.extend({
		defaults: {
			resolve: 'skip'
		},
		initialize: function() {

		},
		parse: function(data) {
			return _.reduce(data, function(memo, value, index) {
				memo[MODEL_KEYS[index]] = value;
				return memo;
			}, {});
		},
		getInt: function(attribute) {
			var v = this.get(attribute);
			return _.isNumber(v) ? v : 0;
		},
		status: function() {
			if (this.get('ignore')) {
				return "ignored";
			} else if (!this.get('sync_time')) {
				return "unknown";
			}
			var rv = this.getInt('remote_version');
			var lv = this.getInt('local_version');
			var srv = this.getInt('sync_remote_version');
			var slv = this.getInt('sync_local_version');
			if (rv && !lv) {
				// can't find local copy
				return "missing"
			} else if (lv && !rv) {
				// can't find remote copy
				return "new"
			} else if (rv > srv && lv > slv) {
				// both remote && local are out of sync
				return "conflict"
			} else if (rv > srv) {
				// local in-sync, but remote out of sync
				return "outdated"
			} else if (lv > slv) {
				// local out of sync, but remote in sync
				return "modified"
			} else if (rv == srv && lv == slv) {
				return "synced"
			}
			return "unknown"
		}
	});
	
	var WikiSyncCollection = Backbone.Collection.extend({
		model: WikiSyncModel,
		formToken: null,
		initialize: function(models, opts) {
			this.url = opts.url;
		},
		comparator: function(model) {
			return model.get('name');
		},
		sync: function(model, resolveAs) {
			if (!_.isString(resolveAs)) {
				resolveAs = model.status();
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
					model.trigger('complete', model, status, action);
				}
			});
		},
		ignore: function(models, isIgnore) {
			var self = this;
			var batch = models.splice(0, 10);
			var data = _.map(batch, function(model) {
				return { name:'name', value:model.get('name') };
			});
			data.push({ name:'action', value:'resolve' });
			data.push({ name:'status', value:isIgnore ? 'ignore' : 'unignore' });
			this._post({ 
				data:data,
				beforeSend: function() {
					_.each(batch, function(model) {
						model.trigger('progress', model);
					});
				},
				complete: function(xhr, status) {
					_.each(batch, function(model) {
						model.trigger('complete', model, status, isIgnore ? 'ignore' : 'unignore');
					});
					if (models.length) {
						self.ignore(models, isIgnore);
					}
				}
			});
		},
		_post: function(opts) {
			if (_.isArray(opts.data)) {
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
								model.set(model.parse(item));
							} else {
								self.add([data], { parse:true });
							}
						});
					},
					error: function(xhr, status, err) {
						/* todo */
						console.log(arguments);
					}
				}, opts)
			);
			
		}
	});
	
	var WikiSyncView = Backbone.View.extend({
		events: {
			'click .ignore-item,.ignore-all': 'onIgnore',
			'click .unignore-item,.unignore-all': 'onIgnore',
			'click button.submit': 'onSync',
			'change input.resolve': 'onResolve',
			'change #filter-conflict-resolve': 'onGlobalResolve',
			'change input.filter': 'onFilter'
		},
		initialize: function(opts) {
			_.bindAll(this);
			this.localUrl = opts['localUrl'] || '';
			this.remoteUrl = opts['remoteUrl'] || '';
			this.nodeTemplate = _.template(TREE_NODE_TEMPLATE);
			this.nestedNodeTemplate = _.template(TREE_NESTED_NODE_TEMPLATE);
			this.$controls = this.$('#wikisync-controls');
			this.$list = this.$('#wikisync-list');
			this.collection.formToken = this.$controls.find('input[name~=__FORM_TOKEN]').val();
			this.collection.bind('all', this.onCollectionChange);
		},
		render: function() {
			this.renderTree();
			return this;
		},
		renderTree: function() {
			var filterKeys = {};
			this.$('input.filter').each(function() {
				var el = $(this);
				var val = $(this).val();
				if (val && el.is(':checked')) {
					filterKeys[val] = true;
				}
			});
			var filtered = this.collection.filter(function(model) {
				return filterKeys[model.status()];
			});
			var filterHash = _.map(filtered, function(model) {
				return model.cid;
			}).join('');
			if (filterHash != this.filterHash) {
				/* avoid expensive redraw by comparing filterHash */
				var tree = groupByTokenHierachy(filtered);
				var content = _.map(tree, this.formatTreeNode);
				this.$list.find('div.item-wrapper').unbind('mouseover mouseout');
				this.$list.empty().html(content.join(''));
				this.$list.find('div.item-wrapper').hover(this.onListOver, this.onListOut);
				this.filterHash = filterHash;
			}
			return this;
		},
		formatTreeNode: function(node) {
			if (_.isArray(node)) {
				var data = {
					cid: _.uniqueId("grouped"),
					name: node[0],
					nested: _.map(node[1], this.formatTreeNode, this).join('')
				};
				return this.nestedNodeTemplate(data);
			} else {
				var data = node.toJSON();
				var name = node.get('name');
				data['cid'] = node.cid;
				data['status'] = node.status();
				data['localUrl'] = formatUrl(this.localUrl, name);
				data['remoteUrl'] = formatUrl(this.remoteUrl, 'wiki', name);
				return this.nodeTemplate(data);
			}
		},
		sync: function(bool) {
			if (_.isUndefined(bool)) {
				bool = !_.isArray(this.syncPending);
			}
			if (bool == _.isArray(this.syncPending)) return;
			var inputs = this.$('input,select');
			if (!bool) {
				this.$el.removeClass('wikisync-progress');
				inputs.removeAttr('disabled');
				this.syncPending = null;
			} else {
				this.$el.addClass('wikisync-progress');
				inputs.attr('disabled', 'disabled');
				var collection = this.collection,
					pending = [],
					el, model;
				this.$list.find('li').each(function() {
					el = $(this);
					if (el.is('.grouped,.ignored,.synced')) {
						return true;
					}
					model = collection.getByCid(el.attr('id'));
					if (!model) return true;
					pending.push(model);
					
				});
				this.syncPending = pending;
				this.errors = 0;
				this.syncNext();
			}
			return this;
		},
		syncNext: function() {
			if (this.errors > 5) {
				alert('Synchronization is stopped as too many error has occurred');
				this.sync(false);
			}
			var model = this.syncPending ? this.syncPending.shift() : null;
			if (!model) {
				this.sync(false);
				alert('Synchronization complete');
			} else {
				var resolveAs;
				if (model.status() == 'conflict') {
					resolveAs = $('#filter-conflict-resolve').val() || model.get('resolve');
					if (resolveAs == 'skip') {
						this.syncNext();
						return;
					}
				}
				this.collection.sync(model, resolveAs);
			}
		},
		onCollectionChange: function(type, model, status, action) {
			var el = model && model.cid ? this.$('#' + model.cid) : null;
			var wrapper = el.find('.item-wrapper');
			if (type == 'change') {
				if (el.length) {
					el.find('div.item-wrapper').unbind('mouseover mouseout');
					var newEl = $(this.formatTreeNode(model)).hide();
					el.replaceWith(newEl);
					newEl.find('div.item-wrapper').hover(this.onListOver, this.onListOut);
					newEl.fadeIn();
				}
			} else if (type == 'progress') {
				wrapper.append('<i>In progress..</i>');
			} else if (type == 'complete') {
				if (status != 'success') {
					this.error++;
				}
				switch(action) {
					case 'pull':
						wrapper.append('<i> (updated with newer version from remote server)</i>');
						break;
					case 'push':
						wrapper.append('<i> (posted to remote server)</i>');
						break;
					case 'ignore':
						wrapper.append('<i> (is now ignored)</i>');
						break;
					case 'unignore':
						wrapper.append('<i> (is not unignored)</i>');
						break;
				}
				if (this.syncPending) {
					this.syncNext();
				}
			}
		},
		onFilter: function(evt) {
			var el = $(evt.target);
			var li = el.parents('li');
			if (el.is(':checked')) {
				li.addClass('selected');
			} else {
				li.removeClass('selected');
			}
			this.renderTree();
		},
		onSync: function(evt) {
			evt.preventDefault();
			this.sync(!this.syncPending);
		},
		onListOver: function(evt) {
			this.onListOut();
			if (!this.syncPending) {
				this.hover = $(evt.target).parent('li').addClass('hover');
			}
		},
		onListOut: function(evt) {
			if (this.hover) {
				this.hover.removeClass('hover');
				this.hover = null;
			}
		},
		onResolve: function(evt) {
			var input = $(evt.target);
			var id = input.attr('name');
			var model = this.collection.getByCid(id);
			if (model) {
				model.set({ resolve:input.val() }, { silent:true });
			}
		},
		onGlobalResolve: function(evt) {
			var val = $(evt.target).val(),
				conflicts = this.collection.filter(function(model) {
					return model.status() == 'conflict';
				});
			if (val) {
				_.each(conflicts, function(model) {
					this.$('#' + model.cid + ' input.resolve')
						.val([val])
						.attr('disabled', 'disabled');
				}, this);
			} else {
				_.each(conflicts, function(model) {
					val = model.get('resolve') || 'skip';
					this.$('#' + model.cid + ' input.resolve')
						.removeAttr('disabled')
						.val([val]);
				}, this);
			}
		},
		onIgnore: function(evt) {
			evt.preventDefault();
			var target = $(evt.target);
			var isIgnore = true;
			var isGlobal = !target.parent().is('.controls');
			var li = isGlobal ? this.$list : target.parents('li:first');
			if (target.hasClass('ignore-all')) {
				li = li.find('li');
			} else if (target.hasClass('unignore-all')) {
				li = li.find('li');
				isIgnore = false
			} else if (target.hasClass('unignore-item')) {
				isIgnore = false;
			}
			var clz = isIgnore ? 'ignored' : 'unignored';
			var models = [];
			_.each(li, function(el) {
				el = $(el);
				if (el.hasClass('grouped')) return;
				else if (isIgnore && el.hasClass('ignored')) return;
				else if (!isIgnore && !el.hasClass('ignored')) return;
				models.push(this.collection.getByCid(el.attr('id')));
			}, this);
			var num = models.length;
			var verb = isIgnore ? 'ignored' : 'unignored';
			if (num) {
				if (num > 30) {
					if (!confirm('Do you want to ' + verb + ' ' + num + ' wikies?')) {
						return;
					}
				}
				this.collection.ignore(models, isIgnore);
			} else {
				alert('All wikies are already ' + verb);
			}
		}
	});
	
	var root = this;
	root.wikisync = {
		WikiSyncModel: WikiSyncModel,
		WikiSyncCollection: WikiSyncCollection,
		WikiSyncView: WikiSyncView
	};
	
}());