odoo.define('altanmia_researches_library.custom_filter', function (require) {
    'use strict';
    

    var core = require('web.core');
    var qweb = core.qweb;
    var publicWidget = require('web.public.widget');
    //const Domain = require('web.Domain');
    const Domain = require('@web/core/domain');
    const { serializeDate, serializeDateTime } = require( "@web/core/l10n/dates");


    const { Component, hooks } = owl;
    const { useState } = owl;
    const ajax = require('web.ajax');
    const { DateTime } = luxon;
    const { registry } = require("@web/core/registry");
    const formatters = registry.category("formatters");
    const parsers = registry.category("parsers");
    const dom = require('web.dom');
    
    var _t = core._t;
    var _lt = core._lt;

    const FIELD_TYPES = {
        boolean: "boolean",
        char: "char",
        date: "date",
        datetime: "datetime",
        float: "number",
        id: "id",
        integer: "number",
        html: "char",
        many2many: "char",
        many2one: "char",
        monetary: "number",
        one2many: "char",
        text: "char",
        selection: "selection",
    };
    
    // FilterMenu parameters
    const FIELD_OPERATORS = {
        boolean: [
            { symbol: "=", description: _lt("is true"), value: true },
            { symbol: "!=", description: _lt("is false"), value: true },
        ],
        char: [
            { symbol: "ilike", description: _lt("contains") },
            { symbol: "not ilike", description: _lt("doesn't contain") },
            { symbol: "=", description: _lt("is equal to") },
            { symbol: "!=", description: _lt("is not equal to") },
        ],
        date: [
            { symbol: "=", description: _lt("is equal to") },
            { symbol: "!=", description: _lt("is not equal to") },
            { symbol: ">", description: _lt("is after") },
            { symbol: "<", description: _lt("is before") },
            { symbol: ">=", description: _lt("is after or equal to") },
            { symbol: "<=", description: _lt("is before or equal to") },
            { symbol: "between", description: _lt("is between") },
        ],
        datetime: [
            { symbol: "between", description: _lt("is between") },
            { symbol: "=", description: _lt("is equal to") },
            { symbol: "!=", description: _lt("is not equal to") },
            { symbol: ">", description: _lt("is after") },
            { symbol: "<", description: _lt("is before") },
            { symbol: ">=", description: _lt("is after or equal to") },
            { symbol: "<=", description: _lt("is before or equal to") },
        ],
        id: [{ symbol: "=", description: _lt("is") }],
        number: [
            { symbol: "=", description: _lt("is equal to") },
            { symbol: "!=", description: _lt("is not equal to") },
            { symbol: ">", description: _lt("greater than") },
            { symbol: "<", description: _lt("less than") },
            { symbol: ">=", description: _lt("greater than or equal to") },
            { symbol: "<=", description: _lt("less than or equal to") },
        ],
        selection: [
            { symbol: "=", description: _lt("is") },
            { symbol: "!=", description: _lt("is not") },
        ],
    };

    const parseField = (field, value, opts = {}) => {
        if (FIELD_TYPES[field.type] === "char") {
            return value;
        }
        const type = field.type === "id" ? "integer" : field.type;
        const parse = parsers.contains(type) ? parsers.get(type) : (v) => v;
        return parse(value, { field, ...opts });
    };
    
    const formatField = (field, value, opts = {}) => {
        if (FIELD_TYPES[field.type] === "char") {
            return value;
        }
        if (field.type === "date"){
            opts.format="yyyy LLL dd";
        }
        const type = field.type === "id" ? "integer" : field.type;
        const format = formatters.contains(type) ? formatters.get(type) : (v) => v;
        return format(value, { field, ...opts });
    };

    publicWidget.registry.websiteResearchFilter = publicWidget.Widget.extend({
        selector: '.o_portal',
        template: [ 'altanmia_researches_library/static/src/xml/condition_line.xml',
                    'altanmia_researches_library.researches_list'],
        events: {
            'click #filter_btn': '_onFilterShow',
            'click #close_filter_btn': '_onFilterShow',
            'click #btn-apply': '_onApply',
            'click #and-btn': '_andCondition',
            'click .btn-expand': '_expand',
            'click .or-btn': '_orCondition',
            'click .cnd-delete': '_onRemoveCondition',
            'change .cnd-field':'_onFieldSelect',
            'change .cnd-operator':'_onOperatorSelect',
            'change .datetimepicker-input':'_onDateChanged',
            'change .cnd-value':'_onValueChange',
        },
        
        init: function () {
            this.dateOptions = {
                calendarWeeks: true,
                icons: {
                    close: 'fa fa-check primary',
                },
                locale: moment.locale(),
                dateFormat: 'yy M dd',
                sideBySide: true,
                buttons: {
                    showClear: true,
                    showClose: true,
                    showToday: true,
                },
            };

            $(".research-items").first().addClass('show');
            $(".groupby-bar").first().find('.btn-expand').removeClass('fa-chevron-circle-right');
            $(".groupby-bar").first().find('.btn-expand').addClass('fa-chevron-circle-down');

            this.hide_filter = true;
            this.conditions = [];
            var self = this;
            ajax.jsonRpc('/researches/search_fileds', 'call')
                .then(function (result) {
                    
                    self.fields = Object.values(result)
                    .filter((field) => self.validateField(field))
                    .sort(({ string: a }, { string: b }) => (a > b ? 1 : a < b ? -1 : 0));
                    self.OPERATORS = FIELD_OPERATORS;
                    self.FIELD_TYPES = FIELD_TYPES;
        
                    // Add first condition
                    self.addNewCondition();
                });
        },

        addNewCondition: function(cnd_index) {
            const condition   = {
                      field: 0,
                      operator: 0,
                      or_conditions: []
                  }
            this.setDefaultValue(condition);

            var cdn = this.conditions[ parseInt(cnd_index)]

            if (cdn === undefined){
                var length =  this.conditions.push(condition);
                length --;
                this._renderFilter(condition, length);
            }else {
                var length =  cdn.or_conditions.push(condition);
                length--;
                this._renderFilter(condition, length, cnd_index);
            }
        },

        _andCondition: function() {
            this.addNewCondition();
        },

        _orCondition: function(ev) {
            var cnd_index = ev.currentTarget.dataset.cndindex;            
            this.addNewCondition(cnd_index);
        },

        _expand: function(ev) {
            var $target = $(ev.currentTarget);
            var group =  ev.currentTarget.dataset.group;
            if($target.hasClass('fa-chevron-circle-down')){
                $target.addClass('fa-chevron-circle-right');
                $target.removeClass('fa-chevron-circle-down');
                $('#'+group).toggleClass('show');
            }else{
                $target.removeClass('fa-chevron-circle-right');
                $target.addClass('fa-chevron-circle-down');
                $('#'+group).toggleClass('show');
            }
        },

        validateField: function(field) {
            return (
                 FIELD_TYPES[field.type] && field.name !== "id"
            );
        },


        setDefaultValue:function(condition) {
            const field = this.fields[condition.field];
            const genericType = FIELD_TYPES[field.type];
            const operator = FIELD_OPERATORS[genericType][condition.operator];
            // Logical value
            switch (genericType) {
                case "id":
                case "number": {
                    condition.value = 0;
                    break;
                }
                case "date":
                case "datetime": {
                    condition.value = [DateTime.local()];
                    if (operator.symbol === "between") {
                        condition.value.push(DateTime.local());
                    }
                    if (genericType === "datetime") {
                        condition.value[0].set({ hour: 0, minute: 0, second: 0 });
                        if (operator.symbol === "between") {
                            condition.value[1].set({ hour: 23, minute: 59, second: 59 });
                        }
                    }
                    break;
                }
                case "selection": {
                    const [firstValue] = this.fields[condition.field].selection[0];
                    condition.value = firstValue;
                    break;
                }
                default: {
                    condition.value = "";
                }
            }
            // Displayed value (no needed for dates: they are handled by the DatePicker component)
            if (!["date", "datetime"].includes(field.type)) {
                condition.displayedValue = formatField(field, condition.value);
            }
            condition.displayedValue = formatField(field, condition.value);
        },

        _renderFilter:function(condition, index, parent_index){
            var and_condition = (parent_index === undefined)
            var menu = $(qweb.render('altanmia_researches_library.condition_line', {
                condition: condition,
                condition_index: index,
                fields: this.fields,
                isAnd: and_condition,
                OPERATORS: this.OPERATORS,
                FIELD_TYPES: this.FIELD_TYPES,
                parent:and_condition?-1:parent_index
            }));
            if(and_condition){
                this.$('#conditions').append(menu);
            }else{
                this.$('#or_conditions-'+ parent_index).append(menu);
            }
            $('.datetimepicker-input').datepicker(this.dateOptions);
        },

        _refreshFilter:function(condition, index, parent_index){
            var and_condition = (parent_index === undefined )
            var menu = $(qweb.render('altanmia_researches_library.condition_line', {
                condition: condition,
                condition_index: index,
                fields: this.fields,
                isAnd: and_condition,
                OPERATORS: this.OPERATORS,
                FIELD_TYPES: this.FIELD_TYPES,
                parent:and_condition?-1:parent_index
            }));
            return menu;
        },

        _onRemoveCondition: function(ev) {
            var cnd_index = ev.currentTarget.dataset.cndindex; 
            var cnd_and =  ev.currentTarget.dataset.type; 
            if (cnd_and == 'true'){
                this.conditions.splice(cnd_index, 1);    
            }else{
                var parent_index =  parseInt( ev.currentTarget.dataset.parent);
                var cnd = this.conditions[parent_index];
                cnd.or_conditions.splice(cnd_index, 1);
            }
            $(ev.currentTarget).closest(".filter-condition").remove();
        },

        _onFieldSelect: function(ev) {
            var cnd_index = parseInt( ev.currentTarget.dataset.cndindex);  
            var cnd_and =  ev.currentTarget.dataset.type; 
            var parent_index =  parseInt( ev.currentTarget.dataset.parent);
            var condition = (cnd_and == 'true')? this.conditions[cnd_index]: this.conditions[parent_index].or_conditions[cnd_index];
            Object.assign(condition, {
                field: ev.target.selectedIndex,
                operator: 0,
            });
            this.setDefaultValue(condition);
            
            var cnd_ele =(cnd_and == 'true')?this._refreshFilter(condition,cnd_index): this._refreshFilter(condition,cnd_index,parent_index)
            $(ev.currentTarget).closest(".filter-condition").replaceWith(cnd_ele);
            $('.datetimepicker-input').datepicker(this.dateOptions);
        },
        
        _onOperatorSelect:function(ev) {
            var cnd_index = parseInt( ev.currentTarget.dataset.cndindex);  
            var cnd_and =  ev.currentTarget.dataset.type; 
            var parent_index =  parseInt( ev.currentTarget.dataset.parent);
            var condition = (cnd_and == 'true')? this.conditions[cnd_index]: this.conditions[parent_index].or_conditions[cnd_index];
            condition.operator = ev.target.selectedIndex;
            this.setDefaultValue(condition);

            var cnd_ele =(cnd_and == 'true')?this._refreshFilter(condition,cnd_index): this._refreshFilter(condition,cnd_index,parent_index)
            $(ev.currentTarget).closest(".filter-condition").replaceWith(cnd_ele);
            $('.datetimepicker-input').datepicker(this.dateOptions);
        },

        _onDateChanged: function( ev) {
            var cnd_index = parseInt( ev.currentTarget.dataset.cndindex);  
            var cnd_and =  ev.currentTarget.dataset.type; 
            var valueIndex = parseInt(ev.currentTarget.dataset.valueindex); 
            var parent_index =  parseInt( ev.currentTarget.dataset.parent);
            var condition = (cnd_and == 'true')? this.conditions[cnd_index]: this.conditions[parent_index].or_conditions[cnd_index];
            condition.value[valueIndex] = DateTime.fromFormat(ev.currentTarget.value, 'yyyy LLL dd', { zone: "utc" });
        },

        _onValueChange: function( ev) {
            var cnd_index = parseInt( ev.currentTarget.dataset.cndindex);  
            var cnd_and =  ev.currentTarget.dataset.type; 
            var parent_index =  parseInt( ev.currentTarget.dataset.parent);
            var condition = (cnd_and == 'true')? this.conditions[cnd_index]: this.conditions[parent_index].or_conditions[cnd_index];
            if (!ev.target.value) {
                return this.setDefaultValue(condition);
            }
            const field = this.fields[condition.field];
            try {
                const parsed = parseField(field, ev.target.value);
                const formatted = formatField(field, parsed);
                // Only updates values if it can be correctly parsed and formatted.
                condition.value = parsed;
                condition.displayedValue = formatted;
            } catch (err) {
                // Parsing error: nothing is done
            }
            ev.target.value = condition.displayedValue;
        },

        _onFilterShow: function(ev){
			/*
            var order={
                order_id:1,
                lines:[
                    {
                        product_id:153,
                        qty:3
                    },
                    {
                        product_id:152,
                        qty:2
                    }
                ]
            }
			
            ajax.jsonRpc('/product/laravel/order', 'call', {'order':order})
                .then(function (result) {
                    $("#research_result").html(result);
                });
			*/
            this.hide_filter = !this.hide_filter;
            this.$('#filter_form').toggleClass('d-none');
            this.$('.navbar').toggleClass('d-none');
        },

        _onApply: function() {
            const $button = this.$target.find('.custom-filter-apply');
            $button.addClass('disabled') // !compatibility
                   .attr('disabled', 'disabled');
            this.restoreBtnLoading = dom.addButtonLoadingEffect($button[0]);

            this.conditions.forEach(cnd => {
                cnd.domain = this._toDomain(cnd);
            });
            var self = this;
            ajax.jsonRpc('/researches/custom_filter', 'call', {'conditions':this.conditions})
                .then(function (result) {
                    $("#research_result").html(result);
                    $(".documents_pager").toggleClass('d-none');
                    self.restoreBtnLoading();
                });
        },

        _toDomain: function(condition){
            const field = this.fields[condition.field];
            const genericType = this.FIELD_TYPES[field.type];
            const operator = this.OPERATORS[genericType][condition.operator];
            const descriptionArray = [field.string, operator.description.toString()];
            const domainArray = [];
            let domainValue;
            // Field type specifics
            if ("value" in operator) {
                domainValue = [operator.value];
                // No description to push here
            } else if (["date", "datetime"].includes(genericType)) {
                const serialize = genericType === "date" ? serializeDate : serializeDateTime;
                
                domainValue = condition.value.map(serialize);
                descriptionArray.push(
                    `"${condition.value
                        .map((val) => formatField(field, val, { timezone: true }))
                        .join(" " + _t("and") + " ")}"`
                );
            } else {
                domainValue = [condition.value];
                descriptionArray.push(`"${condition.value}"`);
            }
            // Operator specifics
            if (operator.symbol === "between") {
                domainArray.push(
                    [field.name, ">=", domainValue[0]],
                    [field.name, "<=", domainValue[1]]
                );
            } else {
                domainArray.push([field.name, operator.symbol, domainValue[0]]);
            }
            condition.or_conditions.forEach(cnd => {
                cnd.domain = this._toDomain(cnd);
            });
            return domainArray;
        }
    });
});