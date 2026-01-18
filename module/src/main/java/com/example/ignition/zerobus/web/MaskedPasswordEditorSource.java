package com.example.ignition.zerobus.web;

import com.inductiveautomation.ignition.gateway.localdb.persistence.FormMeta;
import com.inductiveautomation.ignition.gateway.web.components.RecordEditMode;
import com.inductiveautomation.ignition.gateway.web.components.editors.AbstractFormComponentEditor;
import com.inductiveautomation.ignition.gateway.web.components.editors.IEditorSource;
import com.inductiveautomation.ignition.gateway.web.models.IRecordFieldComponent;
import org.apache.wicket.Component;
import org.apache.wicket.markup.ComponentTag;
import org.apache.wicket.markup.html.form.FormComponent;
import org.apache.wicket.markup.html.form.PasswordTextField;
import org.apache.wicket.validation.IValidator;
import simpleorm.dataset.SFieldMeta;
import simpleorm.dataset.SRecordInstance;

/**
 * A password editor for use in the Ignition 8.1 Gateway Config UI that:
 * - renders as a password input
 * - shows a placeholder "*****" (never the actual stored secret)
 *
 * Note: leaving the field blank is handled by ZerobusSettingsPage.onBeforeCommit(),
 * which preserves the existing stored secret on edit.
 */
public class MaskedPasswordEditorSource implements IEditorSource {
    private final int size;
    private final int maxLength;

    public MaskedPasswordEditorSource(int size) {
        this(size, -1);
    }

    public MaskedPasswordEditorSource(int size, int maxLength) {
        this.size = size;
        this.maxLength = maxLength;
    }

    @Override
    public Component newEditorComponent(String id, RecordEditMode mode, SRecordInstance record, FormMeta formMeta) {
        return new StringEditor(id, formMeta, mode, record);
    }

    private final class StringEditor extends AbstractFormComponentEditor {
        private StringEditor(String id, FormMeta formMeta, RecordEditMode mode, SRecordInstance record) {
            super(id, formMeta, mode, record);
        }

        @Override
        protected FormComponent createFormComponent(String id) {
            return new PersistentFieldPasswordTextField(id);
        }

        private final class PersistentFieldPasswordTextField extends PasswordTextField implements IRecordFieldComponent {
            private PersistentFieldPasswordTextField(String id) {
                super(id);
            }

            @Override
            public SFieldMeta getFieldMeta() {
                return getFormMeta().getField();
            }

            @Override
            protected void onComponentTag(ComponentTag tag) {
                tag.put("type", "password");
                tag.put("size", size);
                tag.put("placeholder", "*****");
                if (maxLength >= 0) {
                    tag.put("maxlength", maxLength);
                }
                super.onComponentTag(tag);
            }

            @Override
            protected boolean shouldTrimInput() {
                return false;
            }
        }
    }
}


