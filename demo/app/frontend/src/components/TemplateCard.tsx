import type { AssetTemplate } from '../services/api';

interface TemplateCardProps {
  template: AssetTemplate;
  onClick: () => void;
}

export default function TemplateCard({ template, onClick }: TemplateCardProps) {
  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onClick(); } }}
      className="bg-surface-card border border-gray-200 rounded-card p-4 cursor-pointer shadow-card
                 hover:border-gray-600 hover:shadow-card-hover transition-all duration-200
                 focus:outline-none focus-visible:ring-2 focus-visible:ring-databricks-primary focus-visible:ring-offset-2"
    >
      <h3 className="font-heading font-semibold text-gray-900">{template.template_name}</h3>
      <p className="text-xs text-gray-500 mt-1">
        {template.base_asset_type.replace(/_/g, ' ')}
      </p>
      {template.description && (
        <p className="text-sm text-gray-600 mt-2 line-clamp-2">{template.description}</p>
      )}
      <div className="flex gap-4 mt-3 text-xs text-gray-500">
        <span>{template.attribute_count} attributes</span>
        <span>{template.asset_count} assets</span>
      </div>
    </div>
  );
}
